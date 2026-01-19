'''
beetleRunBk/main.py
writed by zhywyt at 2025/9/25
coding with utf-8
There are must to use some chinese for comments and strings in this file. please coding with utf-8
中文测试，如果你看得清我，说明你的编码正确。
'''
from fastapi.responses import JSONResponse, FileResponse
from fastapi import FastAPI, Body, Request, File, UploadFile
import json, csv
from contextlib import asynccontextmanager
from sqlmodel import SQLModel, Field, Session, create_engine, select
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import re
from datetime import datetime, timedelta
from collections import OrderedDict
from fastapi.staticfiles import StaticFiles
import os


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield

BACKUP_DIR = "backups"
ARCHIVE_DIR = "archives"
DATABASE_FILE = "test.db"
# current path by dynamic
PWD = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = PWD + "/static"
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")
engine = create_engine("sqlite:///" + DATABASE_FILE)
templates = Jinja2Templates(directory="templates")
date_format = "%Y-%m-%d %H:%M:%S"
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) # used by system
    user_id: int                                    # 
    name: str
class CheckIn(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) # tick gen id
    date: str                                       # date with format yyyy-MM-dd hh:mm:ss
    message_id: int                                 # message id from qq
    user_id: int                                    # qq user id
    order: str                                      # e.g. 打卡 10
    distance: float                                 # distance in km
class BindInfo(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) # tick gen id
    date: str                                       # date with format yyyy-MM-dd hh:mm:ss
    message_id: int                                 # message id from qq
    user_id: int
    name: str
def get_current_week_range() -> str:
    '''
    return the week range same as 9.22-9.28
    '''
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_label = f"{start_of_week.month}.{start_of_week.day}-{end_of_week.month}.{end_of_week.day}"
    return week_label
def get_current_month_range() -> str:
    '''
    return the month range same as 9.1-9.30
    '''
    now = datetime.now()
    start_of_month = now.replace(day=1)
    if now.month == 12:
        end_of_month = now.replace(year=now.year+1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = now.replace(month=now.month+1, day=1) - timedelta(days=1)
    month_label = f"{start_of_month.month}.{start_of_month.day}-{end_of_month.month}.{end_of_month.day}"
    return month_label
def get_current_total_range() -> str:
    '''
    return the total range of checkin table same as 2023.9.1-2024.9.30
    '''
    with Session(engine) as session:
        statement = select(CheckIn).order_by(CheckIn.date)
        results = session.exec(statement)
        checkins = results.all()
        if not checkins:
            return "无数据"
        start_date = datetime.strptime(checkins[0].date, date_format)
        end_date = datetime.strptime(checkins[-1].date, date_format)
        total_label = f"{start_date.year}.{start_date.month}.{start_date.day}-{end_date.year}.{end_date.month}.{end_date.day}"
        return total_label
def get_today_checkin_users()-> list[int]:
    '''
    return the list of user_id who have checkin today
    '''
    with Session(engine) as session:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        statement = select(CheckIn).where(CheckIn.date >= start_of_day.strftime(date_format))
        results = session.exec(statement)
        today_checkins = results.all()
        user_ids = list(set([c.user_id for c in today_checkins]))
        return user_ids
def get_statistics(user_id: int)-> dict:
    '''
    return the statistics of user_id
    '''
    with Session(engine) as session:
        statement = select(CheckIn).where(CheckIn.user_id == user_id)
        results = session.exec(statement)
        checkins = results.all()
        total_distance = sum(checkin.distance for checkin in checkins)
        # 计算本周起始日期（周一）
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        # 统计本周打卡数
        week_checkins = [c for c in checkins if datetime.strptime(c.date, date_format) >= start_of_week]
        return {
            "总计打卡次数": len(checkins),
            "本周打卡次数": len(week_checkins),
            "总距离": total_distance,
            "本周距离": sum(c.distance for c in week_checkins)
        }
def is_binded(user_id: int)->bool:
    '''
    check if the user_id is binded
    '''
    with Session(engine) as session:
        statement = select(User).where(User.user_id == user_id)
        results = session.exec(statement)
        user = results.first()
        return user is not None
def reload_database():
    '''
    reload the database from file
    '''
    global engine
    try:
        # dispose existing connections/pool to release file locks
        engine.dispose()
    except Exception:
        pass
    # recreate engine pointing to the configured database file
    engine = create_engine("sqlite:///" + DATABASE_FILE, connect_args={"check_same_thread": False})
    # ensure metadata exists on the new engine
    SQLModel.metadata.create_all(engine)
@app.post("/web")
async def web_query(data: dict):
    '''
    api for query the databse
    '''
    user_id = data.get("user_id")
    name = data.get("name")
    min_distance = data.get("min_distance")
    max_distance = data.get("max_distance")
    filters = []
    if user_id:
        try:
            user_id = int(user_id)
            filters.append(CheckIn.user_id == user_id)
        except:
            pass
    if min_distance:
        try:
            filters.append(CheckIn.distance >= float(min_distance))
        except:
            pass
    if max_distance:
        try:
            filters.append(CheckIn.distance <= float(max_distance))
        except:
            pass
    with Session(engine) as session:
        stmt = select(CheckIn).order_by(CheckIn.date.desc())
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        checkins = session.exec(stmt).all()
        # 关联用户姓名
        user_map = {u.user_id: u.name for u in session.exec(select(User)).all()}
        result = []
        for c in checkins:
            if name and user_map.get(c.user_id, "") != name:
                continue
            result.append({
                "id": c.id,
                "user_id": c.user_id,
                "name": user_map.get(c.user_id, ""),
                "date": c.date,
                "distance": c.distance,
                "order": c.order
            })
    return JSONResponse(content={"items": result})
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    '''
    page for root
    '''
    return templates.TemplateResponse("web.html", {"request": request})
@app.get("/checkin", response_class=HTMLResponse)
async def read_root(request: Request):
    '''
    page for root
    '''
    return templates.TemplateResponse("checkin.html", {"request": request})
async def get_user_stat_(user_id, request):
    error = None
    stat = None
    name = None
    if not user_id:
        error = "user_id is required."
    elif not is_binded(user_id):
        error = f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。"
    else:
        stat = get_statistics(user_id)
        with Session(engine) as session:
            user = session.exec(select(User).where(User.user_id == user_id)).first()
            if user:
                name = user.name
    return templates.TemplateResponse("user_stat.html", {
        "request": request,
        "stat": stat,
        "error": error,
        "week_label": get_current_week_range(),
        "name": name,
        "user_id": user_id
    })
@app.post("/stat", response_class=HTMLResponse)
async def get_user_stat(data: dict, request: Request):
    '''
    return the user statistic page
    data: {"user_id": 123456}
    '''
    user_id = data.get("user_id")
    return await get_user_stat_(user_id, request)
@app.get("/stat", response_class=HTMLResponse)
async def get_user_stat_get(request: Request):
    '''
    return the user statistic page
    query user_id: ?user_id=123456
    '''
    user_id = request.query_params.get("user_id")
    return await get_user_stat_(user_id, request)
@app.post("/bind", response_class=HTMLResponse)
async def bind_user(data: BindInfo, request: Request):
    '''
    bind the user_id with name
    data: {"user_id": 123456, "name": "zhywyt"}
    '''
    name = data.name
    user_id = data.user_id
    # 检查名字，要求为：中文英文数字组合，不多于二十个字符
    if not re.match(r'^[\w\s_]{1,10}$', name):
        return templates.TemplateResponse("bind_fail.html", {
            "request": request,
            "error": "名字只能包含中文、英文、数字和下划线，且不多于10个字符。"
        })
    if is_binded(user_id):
        # 删除User表项，重新绑定
        with Session(engine) as session:
            statement = select(User).where(User.user_id == user_id)
            results = session.exec(statement)
            user = results.first()
            if user:
                session.delete(user)
                session.commit()
    with Session(engine) as session:
        session.add(data)
        session.commit()
        session.refresh(data)
        # 更新User表
        user = User(user_id=user_id, name=name)
        session.add(user)
        session.commit()
        session.refresh(user)
        # 计算当前User表总人数
        count = len(session.exec(select(User)).all())
    return templates.TemplateResponse("bind_success.html", {
        "request": request,
        "name": name,
        "user_id": user_id,
        "count": count
    })
# 批量打卡接口：上传CSV文件，自动处理
@app.post("/checkin_csv")
async def checkin_csv(request: Request, file: UploadFile | None = File(default=None)):
    '''
    接收CSV文件，批量打卡。CSV需包含表头：user_id,message_id,order,distance,date
    支持表单字段名 `file` 或 `csvfile`。对空文件与多种编码做容错处理。
    该接口不处理当日覆盖操作，只往表中添加，出现错误可以及时删除。
    '''
    # Try to obtain the UploadFile from common field names if not provided
    upload = file
    if upload is None:
        # attempt to get under alternate field name
        form = await request.form()
        if 'csvfile' in form:
            maybe = form['csvfile']
            if isinstance(maybe, UploadFile):
                upload = maybe
        elif 'file' in form and isinstance(form['file'], UploadFile):
            upload = form['file']

    if upload is None:
        return JSONResponse(content={"success": [], "error": ["没有上传文件，请使用字段名 'file' 或 'csvfile' 上传 CSV。"]}, status_code=400)

    content = await upload.read()
    if not content:
        return JSONResponse(content={"success": [], "error": ["上传的文件为空。请检查文件是否包含内容。"]}, status_code=400)

    # Try a few common encodings
    decode_errors = []
    text = None
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            text = content.decode(enc)
            break
        except Exception as e:
            decode_errors.append(f"{enc}: {str(e)}")
    if text is None:
        return JSONResponse(content={"success": [], "error": [f"无法解码上传文件，尝试的编码失败：{decode_errors}"]}, status_code=400)

    lines = text.splitlines()
    try:
        reader = csv.DictReader(lines)
    except Exception as e:
        return JSONResponse(content={"success": [], "error": [f"解析 CSV 失败：{str(e)}"]}, status_code=400)

    results = []
    errors = []
    # iterate with index starting at 1 to match user-facing line numbers (excluding header)
    for idx, row in enumerate(reader, 1):
        try:
            if not row:
                errors.append(f"第{idx}行: 空行")
                continue
            # 构造数据并做基本校验
            try:
                uid = int(row.get("user_id", ""))
            except:
                raise ValueError("user_id 无效或缺失")
            try:
                mid = int(row.get("message_id", ""))
            except:
                raise ValueError("message_id 无效或缺失")
            order = row.get("order", "")
            distance = row.get("distance", "")
            date_s = row.get("date", "")
            if not date_s:
                raise ValueError("date 缺失")

            data = {
                "user_id": uid,
                "message_id": mid,
                "order": order,
                "distance": distance,
                "date": date_s
            }

            # 复用 check_in 逻辑 but without calling the endpoint: validate bind and parse date
            checkin = CheckIn(**data)
            if not is_binded(checkin.user_id):
                errors.append(f"第{idx}行: 用户未绑定 user_id={checkin.user_id}")
                continue
            # validate date
            try:
                dt = datetime.strptime(checkin.date, date_format)
            except Exception as e:
                raise ValueError(f"日期格式错误: {str(e)}，期望格式: {date_format}")
            checkin.date = dt.strftime(date_format)

            # try to convert distance similarly to check_in endpoint
            if type(checkin.distance) != float:
                dist_str = str(checkin.distance)
                scale = 1
                match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(km|公里|千米)', dist_str)
                if not match:
                    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(英里|miles|mile)', dist_str)
                    scale = 1.60934
                if not match:
                    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(m|米)', dist_str)
                    scale = 0.001
                if match:
                    checkin.distance = float(match.group(1)) * scale
                else:
                    raise ValueError(f"无法解析距离: {dist_str}")

            with Session(engine) as session:
                session.add(checkin)
                session.commit()
                session.refresh(checkin)
            # return structured result for frontend
            results.append({
                "line": idx,
                "user_id": checkin.user_id,
                "record_id": checkin.id,
                "date": checkin.date,
                "distance": checkin.distance,
                "message": f"打卡成功 user_id={checkin.user_id}"
            })
        except Exception as e:
            errors.append(f"第{idx}行: 错误 {str(e)}")
    return JSONResponse(content={"success": results, "error": errors})


@app.get('/checkin_template')
async def get_checkin_template():
    """Return the CSV template file for batch checkin.

    The file is expected to be at static/files/template_checkin.csv under the project root.
    """
    import os
    # absolute path to the template file inside the mounted static directory
    template_path = os.path.join(os.path.dirname(__file__), 'static', 'files', 'template_checkin.csv')
    if not os.path.exists(template_path):
        return JSONResponse(content={"error": "template not found"}, status_code=404)
    # FileResponse will set appropriate headers for download
    return FileResponse(template_path, media_type='text/csv', filename='template_checkin.csv')
@app.post("/checkin", response_class=HTMLResponse)
async def check_in(data: dict, request: Request)-> HTMLResponse:
    '''
    checkin api
    will parse the distance if not float, support format same as: 5.08km 5.08公里 21.095千米 5000m 5000米 3.1英里 3.5mile 3.8miles
    data: {"message_id": 123456, "user_id": 123456, "order": "打卡 10km", "distance": 5.08}
    '''
    error = None
    message = None
    start_time = datetime.now()
    if type(data.get("distance")) != float:
        # try to parse 5.08km 5.08公里
        scale = 1
        dist_str = str(data.get("distance"))
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(km|公里|千米)', dist_str)
        if not match:
            match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(英里|miles|mile)', dist_str)
            scale = 1.60934
        if not match:
            match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(m|米)', dist_str)
            scale = 0.001
        if match:
            data["distance"] = float(match.group(1))*scale
            if data["distance"] < 0.001:
                error = f"距离必须大于1m，当前距离: {str(data.get('distance'))}km"
            elif data["distance"] > 100:
                error = f"距离过大，请联系管理员手动添加: {str(data.get('distance'))}"
        else:
            error = f"无法解析距离: {str(data.get('distance'))}，示例： 5.08km | 5.08公里 | 21.095千米 | 5000m | 5000米 | 3.1英里 | 3.5mile | 3.8miles"
        if error != None:
            return templates.TemplateResponse("checkin/checkin_fail.html", {
                "request": request,
                "stat": None,
                "error": error,
                "solve_time": (datetime.now() - start_time).total_seconds(),
            })
    checkin = CheckIn(**data)
    if not is_binded(checkin.user_id):
        return templates.TemplateResponse("checkin/checkin_fail.html", {
            "request": request,
            "stat": None,
            "error": f"{checkin.user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    # This server is UTC+8, then you need not add 8 hours. # check the date if is not UTC+8, convert it to UTC+8
    dt = datetime.strptime(checkin.date, date_format)
    # dt = dt + timedelta(hours=8)
    checkin.date = dt.strftime(date_format)
    # 检查今天是否打过卡了
    checked_users = get_today_checkin_users()
    # 检查今天已经打的人数
    checked_user_num = len(checked_users)
    with Session(engine) as session:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        statement = select(CheckIn).where(
            (CheckIn.user_id == checkin.user_id) &
            (CheckIn.date >= start_of_day.strftime(date_format))
        )
        results = session.exec(statement)
        today_checkins = results.all()
        if today_checkins:
            # 删除该记录
            for c in today_checkins:
                session.delete(c)
            session.commit()
            message = f"{checkin.user_id} 今天已经打过卡了，打卡记录已覆盖。"
    import random
    css_choices = [
        "checkin/checkin.css",
        # "checkin/checkin2.css",
        # "checkin/checkin3.css",
        # "checkin/checkin4.css",
        # "checkin/checkin5.css",
    ]
    chosen_css = request.url_for('static', path=random.choice(css_choices))
    with Session(engine) as session:
        session.add(checkin)
        session.commit()
        session.refresh(checkin)
        stat = get_statistics(checkin.user_id)
        return templates.TemplateResponse("checkin/checkin.html", {
            "request": request,
            "name": session.exec(select(User).where(User.user_id == checkin.user_id)).first().name,
            "mileage": checkin.distance,
            "message": message,
            "today_checkin_count": checked_user_num,
            "css_style_path": chosen_css,
            "stat": stat,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
async def list_checkins_(user_id, page, size, request)-> HTMLResponse:
    '''
    list the checkins of user_id with pagination
    '''
    start_time = datetime.now()
    try:
        page = int(page)
        size = int(size)
    except:
        page = 1
        size = 10
    if type(page) != int or page < 1:
        page = 1
    if not user_id:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id is required.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    try:
        user_id = int(user_id)
    except:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id must be an integer.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    with Session(engine) as session:
        # 统计数量
        maxpage = len(session.exec(select(CheckIn).where(CheckIn.user_id == user_id)).all()) / size
        page = min(page, int(maxpage) + 1)
        statement = select(CheckIn).where(CheckIn.user_id == user_id).offset((page - 1) * size).limit(size)
        results = session.exec(statement)
        checkins = results.all()
        item = [checkin.model_dump() for checkin in checkins]
        return templates.TemplateResponse("list.html", {
            "request": request,
            "items": item,
            "name": session.exec(select(User).where(User.user_id == user_id)).first().name,
            "page": page,
            "maxpage": int(maxpage) + 1,
            "size": size,
            "user_id": user_id,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    return templates.TemplateResponse("checkin_fail.html", {
        "request": request,
        "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
        "solve_time": (datetime.now() - start_time).total_seconds(),
    })
@app.post("/list", response_class=HTMLResponse)
async def list_checkins(data: dict, request: Request)->HTMLResponse:
    '''
    list post api
    data: {"user_id": 123456, "page": 1, "size": 10}
    '''
    user_id = data.get("user_id")
    page = data.get("page", 1)
    size = data.get("size", 10)
    return await list_checkins_(user_id, page, size, request)
@app.get("/list", response_class=HTMLResponse)
async def list_checkins_get(request: Request):
    '''
    list get api
    query user_id: ?user_id=123456&page=1&size=10
    '''
    user_id = request.query_params.get("user_id")
    page = request.query_params.get("page", 1)
    size = request.query_params.get("size", 10)
    return await list_checkins_(user_id, page, size, request)
@app.get("/rank", response_class=HTMLResponse)
async def get_rank(request: Request):
    '''
    rank get api
    get the top 10 users by total distance
    '''
    # cal solve time
    start_time = datetime.now()
    with Session(engine) as session:
        rank_data = {}
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        # search all id to name map
        for row in session.exec(select(CheckIn).where(
            (CheckIn.date >= start_of_week.strftime(date_format)))
        ).all():
            if row.user_id not in rank_data:
                temp_data = {}
                temp_data["uid"] = row.user_id
                temp_data["dist"] = row.distance
                temp_data["name"] = session.exec(select(User).where(User.user_id == row.user_id)).first().name
                temp_data["checkin_count"] = 1
                rank_data[row.user_id] = temp_data
            else:
                rank_data[row.user_id]["dist"] += row.distance
                rank_data[row.user_id]["checkin_count"] += 1
        # sorted by week_distance
        rank_data = sorted(rank_data.values(), key=lambda x: x["dist"], reverse=True)[:10]
        rank_list = []
        for idx, data in enumerate(rank_data, 1):
            rank_list.append({
                "user_id": data.get("uid", 0),
                "name": data.get("name", ""),
                "checkin_count": data.get("checkin_count", 0),
                "week_distance": data.get("dist", 0),
                "rank": idx,
            })
        return templates.TemplateResponse("rank.html", {
            "request": request,
            "items": rank_list,
            "week_label": get_current_week_range(),
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
@app.post("/rank", response_class=HTMLResponse)
async def post_rank(data:dict, request: Request):
    '''
    this api for admin, will pick all data but not front of 10
    data: {"mode" : "total" or "month" or "week"}
    '''
    mode = data.get("mode", "month")
    start_time = datetime.now()
    if mode not in ["total", "month", "week"]:
        mode = "month"
    with Session(engine) as session:
        # 查询所有用户的总距离和总打卡次数（全时段）
        user_dist = {}
        user_checkin_count = {}
        for row in session.exec(select(CheckIn.user_id, CheckIn.distance)):
            uid = row.user_id
            user_dist[uid] = user_dist.get(uid, 0) + row.distance
            user_checkin_count[uid] = user_checkin_count.get(uid, 0) + 1
        # 查询所有用户姓名
        user_name_map = {u.user_id: u.name for u in session.exec(select(User)).all()}

        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        rank_list = []
        label_key = "week_label"
        label = ""

        # Helper to build and sort rank list by a key
        if mode == "week":
            # build list of users with their week_distance
            temp = []
            for uid in user_dist.keys():
                week_statement = select(CheckIn).where(
                    (CheckIn.user_id == uid) &
                    (CheckIn.date >= start_of_week.strftime(date_format))
                )
                week_checkins = session.exec(week_statement).all()
                week_distance = sum(c.distance for c in week_checkins)
                week_count = len(week_checkins)
                if week_distance < 1:
                    continue
                temp.append({
                    "user_id": uid,
                    "name": user_name_map.get(uid, ""),
                    "checkin_count": week_count,
                    "week_distance": week_distance,
                    "total_distance": user_dist.get(uid, 0),
                })
            # sort by week_distance desc
            temp = sorted(temp, key=lambda x: x["week_distance"], reverse=True)
            for idx, item in enumerate(temp, 1):
                item["rank"] = idx
            rank_list = temp
            label_key = "week_label"
            label = get_current_week_range()

        elif mode == "month":
            temp = []
            for uid in user_dist.keys():
                month_statement = select(CheckIn).where(
                    (CheckIn.user_id == uid) &
                    (CheckIn.date >= start_of_month.strftime(date_format))
                )
                month_checkins = session.exec(month_statement).all()
                month_distance = sum(c.distance for c in month_checkins)
                month_count = len(month_checkins)
                if month_distance < 1:
                    continue
                temp.append({
                    "user_id": uid,
                    "name": user_name_map.get(uid, ""),
                    "checkin_count": month_count,
                    "month_distance": month_distance,
                    "total_distance": user_dist.get(uid, 0),
                })
            temp = sorted(temp, key=lambda x: x["month_distance"], reverse=True)
            for idx, item in enumerate(temp, 1):
                item["rank"] = idx
            rank_list = temp
            label_key = "month_label"
            label = get_current_month_range()

        else:  # total
            temp = []
            for uid, total_distance in user_dist.items():
                total_count = user_checkin_count.get(uid, 0)
                if total_distance < 1:
                    continue
                temp.append({
                    "user_id": uid,
                    "name": user_name_map.get(uid, ""),
                    "checkin_count": total_count,
                    "total_distance": total_distance,
                })
            temp = sorted(temp, key=lambda x: x["total_distance"], reverse=True)
            for idx, item in enumerate(temp, 1):
                item["rank"] = idx
            rank_list = temp
            label_key = "total_label"
            label = get_current_total_range()

        return templates.TemplateResponse("rank.html", {
            "request": request,
            "items": rank_list,
            label_key: label,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
@app.post("/delete", response_class=HTMLResponse)
async def delete_checkin(data: dict, request: Request):
    '''
    delete all checkin data of user_id
    data: {"user_id":123456}
    '''
    user_id = data.get("user_id")
    start_time = datetime.now()
    if type(user_id) != int:
        try:
            user_id = int(user_id)
        except:
            user_id = None
    if not user_id:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id is required.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    deleted_data = []
    with Session(engine) as session:
        # deleted all checkin data
        statement = select(CheckIn).where(CheckIn.user_id == user_id)
        results = session.exec(statement)
        checkins = results.all()
        for checkin in checkins:
            session.delete(checkin)
            deleted_data.append(checkin)
        session.commit()
        return templates.TemplateResponse("delete_checkin_success.html", {
            "request": request,
            "stat": None,
            "deleted_data" : deleted_data,
            "message": f"成功删除 {len(deleted_data)} 条打卡记录。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
@app.post("/erase")
async def erase_checkinfo(data: dict):
    '''
    erase the checkin info record
    data: {"id": 123456}
    '''
    record_id = data.get("id")
    if type(record_id) != int:
        try:
            record_id = int(record_id)
        except:
            record_id = None
    if not record_id:
        return JSONResponse(content={"error": "id is required."}, status_code=400)
    with Session(engine) as session:
        statement = select(CheckIn).where(CheckIn.id == record_id)
        results = session.exec(statement)
        checkin = results.first()
        if not checkin:
            return JSONResponse(content={"error": f"Record with id {record_id} not found."}, status_code=404)
        session.delete(checkin)
        session.commit()
        return JSONResponse(content={"message": f"Record with id {record_id} deleted successfully."})
        
def save_data_base_(request: Request, backup_name=None, backup_dir="backups"):
    '''
    only backup data do not clear checkin table
    '''
    import os
    import shutil
    os.makedirs(backup_dir, exist_ok=True)
    # there is not parse checkin.date need not date_format var
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_name == None:
        backup_name = timestamp
    backup_file = os.path.join(backup_dir, f"backup_{backup_name}.db")
    # get backup file size
    backup_size = 0
    shutil.copy("test.db", backup_file)
    backup_size = os.path.getsize(backup_file)
    return backup_file, backup_size
def load_data_base_(request: Request, backup_name, backup_dir="backups"):
    '''
    load the backup database file
    '''
    import shutil
    start_time = datetime.now()
    backup_file = os.path.join(backup_dir, backup_name)
    if not backup_file:
        return templates.TemplateResponse("checkin/checkin_fail.html", {
            "request": request,
            "error": f"backup_file is required.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    if not os.path.exists(backup_file):
        return templates.TemplateResponse("checkin/checkin_fail.html", {
            "request": request,
            "error": f"backup_file {backup_file} does not exist.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    # dispose engine first to release any open connections to the DB file
    try:
        engine.dispose()
    except Exception:
        pass
    # copy backup file to database file
    shutil.copy(backup_file, DATABASE_FILE)
    # recreate engine / reload metadata
    reload_database()
    return templates.TemplateResponse("load_backup_success.html", {
        "request": request,
        "backup_file": backup_file,
        "message": f"已从 {backup_file} 恢复数据库。",
        "solve_time": (datetime.now() - start_time).total_seconds(),
    })
@app.post("/backup", response_class=HTMLResponse)
async def backup_data(data: dict, request: Request):
    '''
    backup database only, do not clear checkin table
    '''
    start_time = datetime.now()
    backup_name = data.get("backup_name", None)
    backup_file, backup_size = save_data_base_(request, backup_name, BACKUP_DIR)
    return templates.TemplateResponse("backup_success.html", {
        "request": request,
        "backup_file": backup_file,
        "message": f"数据库已备份到 {backup_file}。",
        "backup_size": backup_size,
        "solve_time": (datetime.now() - start_time).total_seconds(),
    })
    
@app.post("/archive", response_class=HTMLResponse)
async def archive_data(data: dict, request:Request):
    '''
    backup database and clear current checkins 
    save the user and bindinfo table
    clear checkin table
    '''
    start_time = datetime.now()
    from sqlmodel import text
    backup_name = data.get("backup_name", None)
    backup_file, backup_size = save_data_base_(request, backup_name, ARCHIVE_DIR)
    with Session(engine) as session:
        sql = 'DELETE FROM checkin'
        session.exec(text(sql))
        session.commit()
        return templates.TemplateResponse("backup_success.html", {
            "request": request,
            "backup_file": backup_file,
            "message": f"数据库已备份到 {backup_file}，并清空了打卡记录。",
            "backup_size": backup_size,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
@app.get("/list_backups", response_class=HTMLResponse)
async def list_backups(request: Request):
    '''
    list all backup files
    '''
    import os
    backup_dir = BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)
    files = os.listdir(backup_dir)
    backup_files = []
    for f in files:
        if f.startswith("backup_") and f.endswith(".db"):
            file_path = os.path.join(backup_dir, f)
            file_size = os.path.getsize(file_path)
            backup_files.append({
                "file_name": f,
                "file_path": file_path,
                "file_size": file_size,
            })
    return templates.TemplateResponse("list_backups.html", {
        "request": request,
        "backup_files": backup_files,
    })
@app.get("/list_archives", response_class=HTMLResponse)
async def list_archives(request: Request):
    '''
    list all archive files
    '''
    import os
    archive_dir = ARCHIVE_DIR
    os.makedirs(archive_dir, exist_ok=True)
    files = os.listdir(archive_dir)
    archive_files = []
    for f in files:
        if f.startswith("backup_") and f.endswith(".db"):
            file_path = os.path.join(archive_dir, f)
            file_size = os.path.getsize(file_path)
            archive_files.append({
                "file_name": f,
                "file_path": file_path,
                "file_size": file_size,
            })
    return templates.TemplateResponse("list_archives.html", {
        "request": request,
        "archive_files": archive_files,
    })
@app.post("/load_backup", response_class=HTMLResponse)
async def load_backup(data: dict, request: Request):
    '''
    load backup database file
    data: {"backup_file": "backup_20230101_120000.db"}
    '''
    backup_name = data.get("backup_file")
    return load_data_base_(request, backup_name, BACKUP_DIR)
@app.post("/load_archive", response_class=HTMLResponse)
async def load_archive(data: dict, request: Request):
    '''
    load archive database file
    data: {"archive_file": "backup_20230101_120000.db"}
    '''
    import os
    import shutil
    archive_file = data.get("archive_file")
    return load_data_base_(request, archive_file, ARCHIVE_DIR)
'''
年度总结
1、打卡总次数
2、打卡总距离
3、0~5km、5~10km、10~21km、21km以上的打卡次数，最常跑的距离区间
4、最长连续打卡天数
5、最远单次打卡距离
6、打卡最多的月份（打卡了多少次）
7、打卡最多的星期几（打卡了多少次）
8、打卡时间分布（早晨、上午、下午、晚上、深夜）
9、每月距离
'''
@app.post("/year_summary", response_class=HTMLResponse)
async def year_summary(data: dict, request: Request):
    '''
    year summary for user_id
    data: {"user_id": 123456, "year": 2023}
    '''
    user_id = data.get("user_id")
    year = data.get("year")
    start_time = datetime.now()
    if type(user_id) != int:
        try:
            user_id = int(user_id)
        except:
            user_id = None
    if not user_id:
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"user_id is required.",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    if not is_binded(user_id):
        return templates.TemplateResponse("checkin_fail.html", {
            "request": request,
            "error": f"{user_id} 还没有绑定，请使用 绑定 姓名 进行绑定。",
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })
    try:
        year = int(year)
    except:
        year = datetime.now().year
    with Session(engine) as session:
        statement = select(CheckIn).where(
            (CheckIn.user_id == user_id) &
            (CheckIn.date >= f"{year}-01-01 00:00:00") &
            (CheckIn.date <= f"{year}-12-31 23:59:59")
        )
        results = session.exec(statement)
        checkins = results.all()
        if not checkins:
            return templates.TemplateResponse("checkin_fail.html", {
                "request": request,
                "error": f"{year} 年没有打卡记录。",
                "solve_time": (datetime.now() - start_time).total_seconds(),
            })
        # 计算各项数据
        total_checkins = len(checkins)
        total_distance = sum(c.distance for c in checkins)
        # 距离区间统计
        distance_ranges = {
            "0~5km": 0,
            "5~10km": 0,
            "10~21km": 0,
            "21km以上": 0
        }
        for c in checkins:
            if c.distance < 5:
                distance_ranges["0~5km"] += 1
            elif c.distance < 10:
                distance_ranges["5~10km"] += 1
            elif c.distance < 21:
                distance_ranges["10~21km"] += 1
            else:
                distance_ranges["21km以上"] += 1
        most_common_range = max(distance_ranges, key=distance_ranges.get)
        # 最长连续打卡天数
        dates = sorted(set([datetime.strptime(c.date, date_format).date() for c in checkins]))
        longest_streak = 0
        current_streak = 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i-1]).days == 1:
                current_streak += 1
            else:
                longest_streak = max(longest_streak, current_streak)
                current_streak = 1
        longest_streak = max(longest_streak, current_streak)
        # 最远单次打卡距离
        max_distance = max(c.distance for c in checkins)
        # 打卡最多的月份
        month_count = {}
        for c in checkins:
            month = datetime.strptime(c.date, date_format).month
            month_count[month] = month_count.get(month, 0) + 1
        most_active_month = max(month_count, key=month_count.get)
        most_active_month_times = month_count[most_active_month]
        # 打卡最多的星期几
        weekday_count = {}
        for c in checkins:
            weekday = datetime.strptime(c.date, date_format).weekday()
            weekday_count[weekday] = weekday_count.get(weekday, 0) + 1
        most_active_weekday = max(weekday_count, key=weekday_count.get)
        most_active_weekday_times = weekday_count[most_active_weekday]
        # 打卡时间分布
        time_distribution = {
            "早晨(5-8点)": 0,
            "上午(8-12点)": 0,
            "下午(12-18点)": 0,
            "晚上(18-22点)": 0,
            "深夜(22-5点)": 0
        }
        for c in checkins:
            hour = datetime.strptime(c.date, date_format).hour
            if 5 <= hour < 8:
                time_distribution["早晨(5-8点)"] += 1
            elif 8 <= hour < 12:
                time_distribution["上午(8-12点)"] += 1
            elif 12 <= hour < 18:
                time_distribution["下午(12-18点)"] += 1
            elif 18 <= hour < 22:
                time_distribution["晚上(18-22点)"] += 1
            else:
                time_distribution["深夜(22-5点)"] += 1
        # 每月距离
        monthly_distance = {m: 0 for m in range(1, 13)}
        for c in checkins:
            month = datetime.strptime(c.date, date_format).month
            monthly_distance[month] += c.distance
        # 每日打卡距离统计（用于日历热力图），按日期字符串有序返回，单位：公里
        daily_counts = {}
        for c in checkins:
            d = datetime.strptime(c.date, date_format).date().isoformat()
            # 累加当天的总距离
            daily_counts[d] = round(daily_counts.get(d, 0) + float(c.distance), 3)
        # 保证按日期升序
        daily_counts = OrderedDict(sorted(daily_counts.items(), key=lambda x: x[0]))
        name = session.exec(select(User).where(User.user_id == user_id)).first().name
        return templates.TemplateResponse("year_summary.html", {
            "request": request,
            "name": name,
            "year": year,
            "total_checkins": total_checkins,
            "total_distance": total_distance,
            "distance_ranges": distance_ranges,
            "most_common_range": most_common_range,
            "longest_streak": longest_streak,
            "max_distance": max_distance,
            "most_active_month": most_active_month,
            "most_active_month_times": most_active_month_times,
            "most_active_weekday": most_active_weekday,
            "most_active_weekday_times": most_active_weekday_times,
            "time_distribution": time_distribution,
            "monthly_distance": monthly_distance,
            "daily_counts": daily_counts,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })


@app.post("/year_summary_all")
async def year_summary_all(data: dict, request: Request):
    '''
    year summary for all users
    data: {"year": 2023}
    返回 JSON 格式的全体成员年度汇总统计
    '''
    year = data.get("year")
    start_time = datetime.now()
    try:
        year = int(year)
    except:
        year = datetime.now().year

    with Session(engine) as session:
        statement = select(CheckIn).where(
            (CheckIn.date >= f"{year}-01-01 00:00:00") &
            (CheckIn.date <= f"{year}-12-31 23:59:59")
        )
        results = session.exec(statement)
        checkins = results.all()
        if not checkins:
            return JSONResponse(content={"error": f"{year} 年没有打卡记录。"}, status_code=404)

        total_checkins = len(checkins)
        total_distance = sum(c.distance for c in checkins)

        distance_ranges = {"0~5km": 0, "5~10km": 0, "10~21km": 0, "21km以上": 0}
        for c in checkins:
            if c.distance < 5:
                distance_ranges["0~5km"] += 1
            elif c.distance < 10:
                distance_ranges["5~10km"] += 1
            elif c.distance < 21:
                distance_ranges["10~21km"] += 1
            else:
                distance_ranges["21km以上"] += 1
        most_common_range = max(distance_ranges, key=distance_ranges.get)

        # 计算每个用户最长连续打卡天数，取最大
        from collections import defaultdict
        user_dates = defaultdict(set)
        for c in checkins:
            user_dates[c.user_id].add(datetime.strptime(c.date, date_format).date())
        longest_streak = 0
        for uid, dateset in user_dates.items():
            dates = sorted(dateset)
            if not dates:
                continue
            current = 1
            local_max = 1
            for i in range(1, len(dates)):
                if (dates[i] - dates[i-1]).days == 1:
                    current += 1
                else:
                    local_max = max(local_max, current)
                    current = 1
            local_max = max(local_max, current)
            longest_streak = max(longest_streak, local_max)

        max_distance = max(c.distance for c in checkins)

        month_count = {}
        weekday_count = {}
        time_distribution = {"早晨(5-8点)": 0, "上午(8-12点)": 0, "下午(12-18点)": 0, "晚上(18-22点)": 0, "深夜(22-5点)": 0}
        monthly_distance = {m: 0 for m in range(1, 13)}
        for c in checkins:
            dt = datetime.strptime(c.date, date_format)
            m = dt.month
            month_count[m] = month_count.get(m, 0) + 1
            wd = dt.weekday()
            weekday_count[wd] = weekday_count.get(wd, 0) + 1
            hour = dt.hour
            if 5 <= hour < 8:
                time_distribution["早晨(5-8点)"] += 1
            elif 8 <= hour < 12:
                time_distribution["上午(8-12点)"] += 1
            elif 12 <= hour < 18:
                time_distribution["下午(12-18点)"] += 1
            elif 18 <= hour < 22:
                time_distribution["晚上(18-22点)"] += 1
            else:
                time_distribution["深夜(22-5点)"] += 1
            monthly_distance[m] += c.distance

        most_active_month = max(month_count, key=month_count.get)
        most_active_month_times = month_count[most_active_month]
        most_active_weekday = max(weekday_count, key=weekday_count.get)
        most_active_weekday_times = weekday_count[most_active_weekday]

        # top users by total distance
        user_dist = {}
        for c in checkins:
            user_dist[c.user_id] = user_dist.get(c.user_id, 0) + c.distance
        top_users = sorted([{"user_id": uid, "total_distance": dist} for uid, dist in user_dist.items()], key=lambda x: x["total_distance"], reverse=True)[:10]

        # 每日打卡距离统计（用于日历热力图），按日期字符串有序返回，单位：公里
        daily_counts = {}
        for c in checkins:
            d = datetime.strptime(c.date, date_format).date().isoformat()
            # 累加当天的总距离
            daily_counts[d] = round(daily_counts.get(d, 0) + float(c.distance), 3)
        # 保证按日期升序
        daily_counts = OrderedDict(sorted(daily_counts.items(), key=lambda x: x[0]))
        name = "全体成员"
        return templates.TemplateResponse("year_summary.html", {
            "request": request,
            "name": name,
            "year": year,
            "total_checkins": total_checkins,
            "total_distance": total_distance,
            "distance_ranges": distance_ranges,
            "most_common_range": most_common_range,
            "longest_streak": longest_streak,
            "max_distance": max_distance,
            "most_active_month": most_active_month,
            "most_active_month_times": most_active_month_times,
            "most_active_weekday": most_active_weekday,
            "most_active_weekday_times": most_active_weekday_times,
            "time_distribution": time_distribution,
            "monthly_distance": monthly_distance,
            "top_users": top_users,
            "daily_counts": daily_counts,
            "solve_time": (datetime.now() - start_time).total_seconds(),
        })