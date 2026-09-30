
from typing import Union, Annotated
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import uvicorn

import scipy.io as scio
import numpy as np
import io
import os
import zipfile
import fnmatch
from pathlib import Path

import app.ScoringTools.scoring_tools as st
from app import auth, storage
from app.auth import require_user

from app.ScoringTools import config

VERBOSE=True

class Item(BaseModel):
  name: str


app = FastAPI()

# Signed session cookie for logged-in user
app.add_middleware(
    SessionMiddleware,
    secret_key=auth.SESSION_SECRET,
    https_only=auth.APP_BASE_URL.startswith("https"),
    same_site="lax",
)

# Keycloak auth routes
app.include_router(auth.router)

# Serve the static frontend
ui_dir = Path(__file__).parent / "static"
app.mount( "/static", StaticFiles( directory=ui_dir ), name="static" )

@app.post("/items/")
async def create_item(item: Item):
    return item

@app.post("/files/")
async def create_file(file: Annotated[bytes, File()]):
  data = st.load_data(file)
  print(data.keys())
  return {"file_size": len(file)}

def load_zip_data(zip_bytes,dataPattern=st.DATA_FILE_PATTERN):
  """
  TODO:Document
  """
  st.log("Loading zip data")
  loaded_data = []
  st.log(f"\tLooking with pattern {dataPattern}")
#  archive = zipfile.ZipFile(contents)
  names = extract_cs_files(zip_bytes, dataPattern)
  
#  dataFiles = [io.BytesIO(n) for _,n in names]
  st.log(f"\tFound {len(names)} files")
  for file,fcont in names:
    st.log(f"\r\033[K\tLoading file: {file}", ending="")
    raw_mat = scio.loadmat(io.BytesIO(fcont),squeeze_me=True,struct_as_record=False)
    loaded_data.append({'potvals':np.squeeze(raw_mat['ts'].potvals),
              'file':os.path.basename(file),
              'pacingLoc':np.squeeze(raw_mat['ts'].pacingLoc)})
  st.log("\n\tDone loading")
  return loaded_data
  
def load_cs_file(f_contents):
  """
  TODO:Document
  """
#  log("Loading ts data")
  
  bytes_io_object = io.BytesIO(f_contents)
  
  return st.load_data(bytes_io_object)

  
  
def extract_cs_files(zip_bytes, dataPattern=st.DATA_FILE_PATTERN):
  """
  Pull every beat file matching the truth glob (config.DATA_FILE_PATTERN, e.g.
  *-cs.mat) out of an uploaded zip. Returns a list of (name, bytes) sorted by
  basename to line up with the truth files, ignoring nested folders and other
  variants
  """
  try:
    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
  except zipfile.BadZipFile:
    raise HTTPException(status_code=400, detail="Uploaded file is not a valid .zip archive.")

  names = [n for n in archive.namelist()
           if not n.endswith("/")
           and "__MACOSX" not in n
           and fnmatch.fnmatch(os.path.basename(n), dataPattern)]
  names.sort(key=os.path.basename)
  if not names:
    raise HTTPException(status_code=400,
              detail=f"The zip contained no files matching '{dataPattern}'.")
  return [(n, archive.read(n)) for n in names]


def resolve_dataset(dataset: str) -> str:
  """
  Check that the requested dataset is one of the challenge datasets and that
  this deployment has its ground truth. Errors here are shown to the user, so
  they name the dataset and never the directory it lives in
  """
  dataset = (dataset or "").strip().lower()
  if not dataset:
    raise HTTPException(status_code=400,
              detail="Choose which ground-truth dataset to score against.")
  if not config.is_known(dataset):
    raise HTTPException(status_code=400,
              detail=f"Unknown dataset '{dataset}'.")
  if not config.is_available(dataset):
    raise HTTPException(status_code=503,
              detail=f"The {config.label(dataset)} ground-truth data is not available "
                      "on this server. Please contact the organizers.")
  return dataset


def summarize(filename, dataset, num_beats, final_score, all_scores):
  """
  Turn run_score() output into a JSON-serializable result for the UI
  """
  components = {}
  for key, info in all_scores.items():
    value = info['value']
    if info['norm'] is not None:
      value = info['norm'](value)
    components[key] = {'score': float(value), 'weight': float(info['weight'])}
  return {'filename': filename,
          'dataset': dataset,
          'dataset_label': config.label(dataset),
          'num_beats': num_beats,
          'final_score': float(final_score),
          'components': components}


@app.get("/datasets")
async def datasets(request: Request):
  """
  The ground-truth datasets a submission can be scored against, for the tabs in
  the UI. Carries labels and availability only, never a data path
  """
  require_user(request)
  return config.describe_all()


@app.post("/uploadfile/")
async def upload_file_content(request: Request,
                              file: UploadFile = File(...),
                              dataset: str = Form("")):
  """
  1. Accept a .zip of *-cs.mat files from a logged-in user, along with the
     ground-truth dataset they picked;
  2. Score it against that dataset with that dataset's metrics;
  3. Persist the upload + score, and return the breakdown
  """
  user = require_user(request)
  dataset = resolve_dataset(dataset)

  contents = await file.read()  # Get zip contents as bytes
#  mats = extract_cs_files(contents)
#  data = [load_cs_file(mat_bytes) for _, mat_bytes in mats]
# TODO: this may need some more reworking to integrate the api to the newer scripts
#  archive = zipfile.ZipFile(io.BytesIO(contents))
  data = load_zip_data(contents)
#  print(f"Loaded {len(data)} beat(s): {[name for name, _ in mats]}")
  if len(data) == 0:
    raise HTTPException(status_code=400,
              detail=f"The zip contained no files matching '{config.DATA_FILE_PATTERN}'.")

  # Load the ground truth for the dataset the user picked. resolve_dataset()
  # already confirmed it is configured and non-empty
  gt_data = st.load_data(config.ground_truth_dir(dataset))

  # Score the uploaded data against the ground-truth
  try:
    final_score,all_scores = config.scorer(dataset)(gt_data,data)
  except st.ECGIDataException as exc:
    # Usually a submission scored against the wrong dataset, or missing beats.
    # Name the dataset so a mismatched tab is obvious from the message alone
    raise HTTPException(status_code=400,
              detail=f"Scoring against the {config.label(dataset)} ground truth failed.\n{exc}")
  
  print(f"Final score {final_score} ({dataset})")
  result = summarize(file.filename, dataset, len(data), final_score, all_scores)

  # Persist the upload + score for this user
  folder = storage.save_submission(user, file.filename, contents, result)
  print(f"Saved submission to {folder}")
  return result
    
@app.get("/")
async def root(request: Request):
  """Require login to view the app; send unauthenticated visitors to Keycloak"""
  if not auth.current_user(request):
    return RedirectResponse(url="/login")
  return FileResponse(ui_dir / "index.html")

@app.get("/me")
async def me(request: Request):
  """Used by the frontend to show who is logged in"""
  user = auth.current_user(request)
  if not user:
    raise HTTPException(status_code=401, detail="Not authenticated")
  return user

@app.get("/submissions")
async def submissions(request: Request):
  """Show the logged-in user's past submissions in the history table"""
  user = require_user(request)
  return storage.list_submissions(user)

@app.get("/leaderboard")
async def leaderboard(request: Request, dataset: str = ""):
  """Every participant's best score on one dataset, for the leaderboard tabs.
  Datasets are ranked separately: each has its own metrics, so their scores
  are not comparable"""
  viewer = require_user(request)
  dataset = (dataset or "").strip().lower()
  if not config.is_known(dataset):
    raise HTTPException(status_code=400, detail=f"Unknown dataset '{dataset}'.")
  # Submissions made with auth disabled belong to the dev stand-in user. They
  # are test runs, so keep them off the board once real logins are on
  hide = (auth.DEV_USER["sub"],) if auth.AUTH_ENABLED else ()
  return storage.leaderboard(dataset, viewer, hide_subs=hide)

@app.get("/leaderboard/overall")
async def overall_leaderboard(request: Request):
  """Participants ranked by the average of their best score on each dataset.
  Only those with a score on every challenge dataset are listed"""
  viewer = require_user(request)
  datasets = {key: config.label(key) for key in config.DATASETS}
  # Same as /leaderboard: keep the dev stand-in user's test runs off the board
  # once real logins are on
  hide = (auth.DEV_USER["sub"],) if auth.AUTH_ENABLED else ()
  return storage.overall_leaderboard(datasets, viewer, hide_subs=hide)



#if __name__ == "__main__":
#   uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
# 
if __name__ == "__main__":
    server_config = uvicorn.Config("main:app", port=8080, log_level="info", reload=True)
    server = uvicorn.Server(server_config)
    server.run()
