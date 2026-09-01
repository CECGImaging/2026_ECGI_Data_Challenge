
from typing import Union, Annotated
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import uvicorn

import scipy.io as scio
import io
import os
import zipfile
import fnmatch
from pathlib import Path

import app.ScoringTools.scoring_tools as st
import app.ScoringTools.utah_score as us
from app import auth, storage
from app.auth import require_user

from .config import TRUE_DATA_DIR, TRUE_DATA_FILES
#TRUE_DATA_DIR="/uufs/sci.utah.edu/projects/comp-cardio/ECGI_Challenge/UtahDataset/Train/Beats/"
#TRUE_DATA_FILES="*-cs.mat"
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
  data = load_cs_file(file)
  print(data.keys())
  return {"file_size": len(file)}
  
def load_cs_file(f_contents):
  """
  TODO:Document
  """
#  log("Loading ts data")
  
  bytes_io_object = io.BytesIO(f_contents)
  
  raw_mat = scio.loadmat(bytes_io_object, squeeze_me=True, struct_as_record=False)
  data= {'potvals':raw_mat['ts'].potvals,
              'file':raw_mat['ts'].filename,
              'leadinfo':raw_mat['ts'].leadinfo}
  return data


def extract_cs_files(zip_bytes):
  """
  Pull every beat file matching the truth glob (TRUE_DATA_FILES, e.g. *-cs.mat)
  out of an uploaded zip. Returns a list of (name, bytes) sorted by basename to
  line up with the truth files, ignoring nested folders and other variants
  """
  try:
    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
  except zipfile.BadZipFile:
    raise HTTPException(status_code=400, detail="Uploaded file is not a valid .zip archive.")

  names = [n for n in archive.namelist()
           if not n.endswith("/")
           and "__MACOSX" not in n
           and fnmatch.fnmatch(os.path.basename(n), TRUE_DATA_FILES)]
  names.sort(key=os.path.basename)
  if not names:
    raise HTTPException(status_code=400,
              detail=f"The zip contained no files matching '{TRUE_DATA_FILES}'.")
  return [(n, archive.read(n)) for n in names]


def summarize(filename, num_beats, final_score, all_scores):
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
          'num_beats': num_beats,
          'final_score': float(final_score),
          'components': components}


@app.post("/uploadfile/")
async def upload_file_content(request: Request, file: UploadFile = File(...)):
  """
  1. Accept a .zip of *-cs.mat files from a logged-in user;
  2. Score it against the ground-truth data;
  3. Persist the upload + score, and return the breakdown
  """
  user = require_user(request)

  contents = await file.read()  # Get zip contents as bytes
  mats = extract_cs_files(contents)
  data = [load_cs_file(mat_bytes) for _, mat_bytes in mats]
  print(f"Loaded {len(data)} beat(s): {[name for name, _ in mats]}")

  #  Handle missing ground-truth data
  if len(st.load(TRUE_DATA_DIR, TRUE_DATA_FILES)) == 0:
    raise HTTPException(status_code=500,
              detail=f"Server has no ground-truth data configured (looked in '{TRUE_DATA_DIR}').")

  # Score the uploaded data against the ground-truth
  try:
    final_score,all_scores = us.run_utah_score(data)
  except us.UtahDataError as exc:
    raise HTTPException(status_code=400, detail=str(exc))
  
  print(f"Final score {final_score}")
  result = summarize(file.filename, len(data), final_score, all_scores)

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

@app.get("/test")
async def test():
  return {"message": "Hello World"}
  

  
    
#if __name__ == "__main__":
#   uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
# 
if __name__ == "__main__":
    config = uvicorn.Config("main:app", port=8080, log_level="info", reload=True)
    server = uvicorn.Server(config)
    server.run()
 
