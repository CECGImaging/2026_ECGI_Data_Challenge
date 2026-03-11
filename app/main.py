
from typing import Union, Annotated
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
import uvicorn

import scipy.io as scio
import io

from .config import TRUE_DATA_DIR, TRUE_DATA_FILES

import app.ScoringTools.utah_score as us

class Item(BaseModel):
  name: str


app = FastAPI()

@app.post("/items/")
async def create_item(item: Item):
    return item

@app.post("/files/")
async def create_file(file: Annotated[bytes, File()]):
  data = load_ts_file(file)
  print(data.keys())
  return {"file_size": len(file)}
  
def load_ts_file(f_contents):
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


@app.post("/uploadfile/")
async def upload_file_content(file: UploadFile):
  contents = await file.read()  # Get file contents as bytes
  data = load_ts_file(contents)
  print(data.keys())
  return {"filename": file.filename, "size": len(contents)}
    
@app.get("/")
async def root():
  return {"message": "it's working.  now do something"}

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
 
