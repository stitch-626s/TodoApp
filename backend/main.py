# FastAIP 服务端主程序
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Annotated, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles


# 类型别名，用于增强代码可读性
DbConnection = sqlite3.Connection | Any
DbCursor = sqlite3.Cursor | Any

app = FastAPI()

# 数据库配置
DB_FILE = 'todo_db.sqlite'

# 挂载静态目录
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def init_db() -> None:
    """
    初始化数据库，若数据库不存在则自动创建
    """

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        '''
            CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            image_path TEXT,
            created_at DATETIME)
        '''
    )
    conn.commit()
    conn.close()

# 程序启动前初始化数据库
init_db()

def get_db_connection() -> DbConnection:
    """
    获取数据库连接
    """

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn
    

@app.get("/todos", response_model=List[Dict[str, Any]])
def read_todos() -> List[Dict[str, Any]]:
    """
    获取所有待办事项，按时间倒序排列
    """

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM todos ORDER BY created_at DESC")
        result = [dict(row) for row in cursor.fetchall()]
        return result
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/todos")
async def create_todo(content: Annotated[str, Form(...)], file: Annotated[Optional[UploadFile], File()] = None) -> Dict[str, str]:
    """
    创建新的待办事项，支持文本和图片
    """

    image_path = ""
    
    # 处理文件上传
    if file:
        file_location = f"uploads/{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())
        image_path = file_location

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO todos (content, image_path, created_at) VALUES (?, ?, ?)"
        cursor.execute(query, (content, image_path, datetime.now()))
        conn.commit()
        return {"status": "success"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8088)