from models import OperationStatusModel,  FileModel
from fastapi import APIRouter
from typing import List
from fastapi import BackgroundTasks, File, UploadFile, HTTPException, Form
from database.crud import read_file, delete_after_read_file, create_file, read_user
import utils
from fastapi.security import OAuth2PasswordBearer
import urllib.parse
from tempfile import NamedTemporaryFile

router = APIRouter(tags=["files"], prefix="/api/files")
auth = OAuth2PasswordBearer(tokenUrl="token")

# dir for saving user files
DIR = "uploaded"
LIMIT = 5

@router.post("/{username}", response_model=OperationStatusModel)
async def add_file(username: str,  task: BackgroundTasks, file: UploadFile = File(...)):
    '''Recieves file from the client and stores in the server
        - username : username for the user
        - file : file to upload
    '''
    # checking if user exists
    user = await read_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # checking if file size is less than limit
    temp_file = NamedTemporaryFile(delete=False)
    file_size: float = 0
    for chunk in file.file:
        file_size += len(chunk)/(1024*1024)
        if file_size>LIMIT or file_size>user["remaining_size"]:
            raise HTTPException(413, detail="file size exceeded")
        temp_file.write(chunk)

    # sometimes filename recieved are enconded in url-like format
    decoded_file_name = urllib.parse.unquote(file.filename)

    # 'file' attributes are filename, file(file-like object)
    file_id = await create_file(file_name=decoded_file_name, username=username, size=float(file_size), dir="uploaded")
       
    # creating background task to save received file
    task.add_task(utils.file_save, file=temp_file,  path=f"{DIR}/{file_id}")
    return {"id": decoded_file_name, "detail": "operation successful"}


@router.get("/{username}/{file_id}", response_model=FileModel)
async def get_file(file_id: str, username: str):
    file = await read_file(file_id=file_id, username=username)
    if file is None:
        raise HTTPException(status_code=404, detail="file not found")
    else:
        return file

@router.delete("/{username}/{file_id}", response_model=OperationStatusModel)
async def remove_file(file_id: str, tasks: BackgroundTasks, username: str):

    # read file content to get path
    file = await read_file(file_id=file_id, username=username)
    if file is None:
        raise HTTPException(status_code=404, detail="user's file not found") 

    # delete by passing file doc
    await delete_after_read_file(file)
    tasks.add_task(utils.file_delete, path=file["path"])
    print(file["file_id"])
    return {"id": file["file_id"], "detail": "operation successful"}