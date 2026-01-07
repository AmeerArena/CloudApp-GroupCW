import azure.functions as func
import datetime
import json
import logging
import os
import uuid
from azure.cosmos import CosmosClient

app = func.FunctionApp()

# Helpers
# Return JSON with propper content type and status code
def json_resp(payload: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload),
        status_code=status,
        mimetype="application/json"
    )

# Safely parse JSON body
# Return (data, error_response)
def parse_json(req: func.HttpRequest):
    try:
        return req.get_json(), None
    except Exception as e:
        logging.error(f"JSON parse error: {e}")
        return None, json_resp({"result": False, "msg": "not a correct json"}, status=400)
     
def get_cosmos_db():
    cosmos_conn = os.environ.get("AzureCosmosDBConnectionString")
    if not cosmos_conn:
        raise ValueError("Missing AzureCosmosDBConnectionString in environment")

    db_name = os.environ.get("DatabaseName", "university-database")

    cosmos = CosmosClient.from_connection_string(cosmos_conn)
    return cosmos.get_database_client(db_name)

# Gets the lecture container -- Remove
def get_lecture_container():
    db = get_cosmos_db()
    lecture_container_name = os.environ.get("LectureContainerName", "lecture")
    return db.get_container_client(lecture_container_name)

# Gets the lecturer container
def get_lecturer_container():
    db = get_cosmos_db()
    lecturer_container_name = os.environ.get("LecturerContainerName", "lecturer")
    return db.get_container_client(lecturer_container_name)

# Gets the student container
def get_student_container():
    db = get_cosmos_db()
    student_container_name = os.environ.get("StudentContainerName", "student")
    return db.get_container_client(student_container_name)

# Fixed uni modules
ALLOWED_MODULES = {
        "BIOM1",
        "BIOM2",
        "BIOM3",
        "COMP1",
        "COMP2",
        "COMP3",
        "ELEC1",
        "ELEC2",
        "ELEC3",
        "MATH1",
        "MATH2",
        "MATH3"
    }

# enroll a student. json: {"name": "string", "password": "string", "modules": ["MODL1","MODL2"]}
@app.route(route="student/enroll", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def student_enroll(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('student/enroll')

    data, err = parse_json(req)
    if err:
        return err

    student_name = (data.get("name") or "").strip()
    student_password = (data.get("password") or "").strip()
    student_modules = data.get("modules") or []

    # Validate student name
    if not student_name:
        return json_resp(
            {"result": False, "msg": "student must have a name"},
            status=400
        )

    # Validate student password
    if not student_password:
        return json_resp(
            {"result": False, "msg": "student must have a password"},
            status=400
        )

    if len(student_password) < 8 or len(student_password) > 12:
        return json_resp(
            {
                "result": False,
                "msg": "password must be between 8 and 12 characters long"
            },
            status=400
        )

    # Validate modules list exist
    if not isinstance(student_modules, list) or len(student_modules) == 0:
        return json_resp(
            {"result": False, "msg": "student must provide modules"},
            status=400
        )

    # Clean modules, remove duplicates
    cleaned_modules = []
    seen = set()

    for m in student_modules:
        if isinstance(m, str):
            mm = m.strip()
            if mm and mm not in seen:
                seen.add(mm)
                cleaned_modules.append(mm)

    if not cleaned_modules:
        return json_resp(
            {"result": False, "msg": "modules must be valid strings"},
            status=400
        )

    # Exactly 4 modules
    if len(cleaned_modules) != 4:
        return json_resp(
            {"result": False, "msg": "students must have 4 modules"},
            status=400
        )

    # Validate modules
    invalid_modules = [m for m in cleaned_modules if m not in ALLOWED_MODULES]
    if invalid_modules:
        return json_resp(
            {
                "result": False,
                "msg": "invalid module(s)",
                "invalid": invalid_modules,
                "allowed": sorted(ALLOWED_MODULES)
            },
            status=400
        )

    StudentContainer = get_student_container()

    # Check if student already exists
    students = list(StudentContainer.query_items(
        query="SELECT * FROM s WHERE s.name = @name",
        parameters=[{"name": "@name", "value": student_name}],
        enable_cross_partition_query=True
    ))

    if students:
        return json_resp(
            {"result": False, "msg": "student already exists"},
            status=409
        )

    # Create student document
    new_student = {
        "id": str(uuid.uuid4()),
        "name": student_name,
        "password": student_password,
        "modules": cleaned_modules,
    }

    StudentContainer.create_item(body=new_student)

    return json_resp({"result": True, "msg": "OK"}, status=201)

# Student login
# Example JSON body: { "name": "Aarfa", "password": "Password1" }
@app.route(route="student/login", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def student_login(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("student/login")

    data, err = parse_json(req)
    if err:
        return err

    student_name = (data.get("name") or "").strip()
    student_password = (data.get("password") or "").strip()

    # Validate student name
    if not student_name:
        return json_resp(
            {"result": False, "msg": "name is required"},
            status=400
        )

    # Validate student password
    if not student_password:
        return json_resp(
            {"result": False, "msg": "password is required"},
            status=400
        )

    StudentContainer = get_student_container()

    students = list(StudentContainer.query_items(
        query="SELECT * FROM s WHERE s.name = @name",
        parameters=[{"name": "@name", "value": student_name}],
        enable_cross_partition_query=True
    ))

    if not students:
        return json_resp(
            {"result": False, "msg": "student not found"},
            status=404
        )

    student = students[0]

    # Check password
    if student.get("password") != student_password:
        return json_resp(
            {"result": False, "msg": "password or name incorrect"},
            status=401
        )

    return json_resp(
        {
            "result": True,
            "msg": "OK",
            "student": {
                "id": student.get("id"),
                "name": student.get("name"),
                "modules": student.get("modules", [])
            }
        },
        status=200
    )


# hire a lecturer
# json: {"name": "string", "password": "string", "modules": ["MOD1","MOD2","MOD3"]}
@app.route(route="lecturer/hire", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecturer_hire(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecturer/hire")

    data, err = parse_json(req)
    if err:
        return err

    lecturer_name = (data.get("name") or "").strip()
    lecturer_password = (data.get("password") or "").strip()
    lecturer_modules = data.get("modules") or []

    # Validate name
    if not lecturer_name:
        return json_resp(
            {"result": False, "msg": "lecturer must have a name"},
            status=400
        )

    # Validate password
    if not lecturer_password:
        return json_resp(
            {"result": False, "msg": "lecturer must have a password"},
            status=400
        )

    if len(lecturer_password) < 8 or len(lecturer_password) > 12:
        return json_resp(
            {"result": False, "msg": "password must be between 8 and 12 characters long"},
            status=400
        )

    # Validate modules list
    if not isinstance(lecturer_modules, list) or len(lecturer_modules) == 0:
        return json_resp(
            {"result": False, "msg": "lecturer must provide modules"},
            status=400
        )

    # Clean modules (remove duplicates)
    cleaned_modules = []
    seen = set()

    for m in lecturer_modules:
        if isinstance(m, str):
            mm = m.strip()
            if mm and mm not in seen:
                seen.add(mm)
                cleaned_modules.append(mm)

    if not cleaned_modules:
        return json_resp(
            {"result": False, "msg": "modules must be valid strings"},
            status=400
        )

    # Exactly 3 modules
    if len(cleaned_modules) != 3:
        return json_resp(
            {"result": False, "msg": "lecturers must have exactly 3 modules"},
            status=400
        )

    # Validate allowed modules
    invalid_modules = [m for m in cleaned_modules if m not in ALLOWED_MODULES]
    if invalid_modules:
        return json_resp(
            {
                "result": False,
                "msg": "invalid module(s)",
                "invalid": invalid_modules,
                "allowed": sorted(ALLOWED_MODULES)
            },
            status=400
        )

    LecturerContainer = get_lecturer_container()

    # Check if lecturer already exists
    lecturers = list(LecturerContainer.query_items(
        query="SELECT * FROM l WHERE l.name = @name",
        parameters=[{"name": "@name", "value": lecturer_name}],
        enable_cross_partition_query=True
    ))

    if lecturers:
        return json_resp(
            {"result": False, "msg": "lecturer already exists"},
            status=409
        )

    # Create lecturer document
    new_lecturer = {
        "id": str(uuid.uuid4()),
        "name": lecturer_name,
        "password": lecturer_password,
        "modules": cleaned_modules,
        "lectures": [],
        "bookings": []
    }

    LecturerContainer.create_item(body=new_lecturer)

    return json_resp({"result": True, "msg": "OK"}, status=201)

# Lecturer login
# JSON body example: { "name": "Dr. Alwash", "password": "Password1" }
@app.route(route="lecturer/login", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecturer_login(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecturer/login")

    data, err = parse_json(req)
    if err:
        return err

    lecturer_name = (data.get("name") or "").strip()
    lecturer_password = (data.get("password") or "").strip()

    # Validate name
    if not lecturer_name:
        return json_resp(
            {"result": False, "msg": "name is required"},
            status=400
        )

    # Validate password
    if not lecturer_password:
        return json_resp(
            {"result": False, "msg": "password is required"},
            status=400
        )

    LecturerContainer = get_lecturer_container()

    lecturers = list(LecturerContainer.query_items(
        query="SELECT * FROM l WHERE l.name = @name",
        parameters=[{"name": "@name", "value": lecturer_name}],
        enable_cross_partition_query=True
    ))

    if not lecturers:
        return json_resp(
            {"result": False, "msg": "lecturer not found"},
            status=404
        )

    lecturer = lecturers[0]

    # Check password
    if lecturer.get("password") != lecturer_password:
        return json_resp(
            {"result": False, "msg": "password or name incorrect"},
            status=401
        )

    # Ensure bookings array exists
    if "bookings" not in lecturer:
        lecturer["bookings"] = []
        LecturerContainer.replace_item(
            item=lecturer["id"],
            body=lecturer
        )

    return json_resp(
        {
            "result": True,
            "msg": "OK",
            "lecturer": {
                "id": lecturer.get("id"),
                "name": lecturer.get("name"),
                "modules": lecturer.get("modules", [])
            }
        },
        status=200
    )

# make a lecture. json:
# {"title": "string", "module": "string", "lecturer": "string", "date": "string", "time": "string"}
@app.route(route="lecture/make", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_make(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('lecture/make')

    try:
        data = req.get_json()
    except Exception as e:
        logging.error(e)
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "not a correct json"})
        )

    lecture_title = data.get("title", "") # lecture title
    lecture_module = data.get("module", "") # the module of the lecture
    lecture_lecturer = data.get("lecturer", "") # lecture title
    lecture_date = data.get("date", "")   # date format YYYY-MM-DD ("2025-11-15")
    lecture_time = data.get("time", "")   # time format HH:MM ("10:00")
    
    if not (lecture_title and lecture_module and lecture_lecturer and lecture_date and lecture_time):
        return func.HttpResponse(json.dumps({"result": False, "msg": "missing required fields"}))
    
    # Check Date format
    try:
        datetime.datetime.strptime(lecture_date, "%Y-%m-%d")
    except ValueError:
        return func.HttpResponse(json.dumps({"result": False, "msg": "date format must be YYYY-MM-DD"}))

    # Check Time format
    try:
        datetime.datetime.strptime(lecture_time, "%H:%M")
    except ValueError:
        return func.HttpResponse(json.dumps({"result": False, "msg": "time format must be HH:MM"}))

    LectureContainer = get_lecture_container()
    LecturerContainer = get_lecturer_container()
    
    lectures = list(LecturerContainer.query_items(
        query = "SELECT * FROM l WHERE l.title = @title",
        parameters = [{"name": "@title", "value": lecture_title}],
        enable_cross_partition_query = True
    ))
    if len(lectures) > 0:
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "lecture already exists"})
        )
    
    lecturers = list(
        LecturerContainer.query_items(
            query="SELECT * FROM c WHERE c.name = @name",
            parameters=[{"name": "@name", "value": lecture_lecturer}],
            enable_cross_partition_query=True
        )
    )
    if not lecturers:
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "lecturer does not exist"})
        )

    lecturer = lecturers[0]

    if lecture_module not in lecturer.get("modules", []):  
        return func.HttpResponse(
            json.dumps({"result": False, "msg": f"lecturer does not teach module '{lecture_module}'"}))

    newLecture = {
        "id": str(uuid.uuid4()),
        "title": lecture_title,
        "module": lecture_module,
        "lecturer": lecturer["name"],
        "date": lecture_date,
        "time": lecture_time
    }

    LectureContainer.create_item(body=newLecture)

    # add lecture title to the lecturer's list of lectures
    lecturer["lectures"].append(lecture_title) 
    LecturerContainer.replace_item(item=lecturer["id"], body=lecturer)

    logging.info('new lecture created')
    return func.HttpResponse(
        json.dumps({"result": True, "msg": "OK"})
    )

@app.route(route="lecture/setModule", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_set_module(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/setModule")

    data, err = parse_json(req)
    if err:
        return err
    
    room_id = (data.get("roomId") or "").strip()
    lecturer_name = (data.get("lecturer") or "").strip()
    module = (data.get("module") or "").strip()

    if not room_id:
        return json_resp({"result": False, "msg": "roomId is required"}, status=400)
    if not lecturer_name:
        return json_resp({"result": False, "msg": "lecturer is required"}, status=400)
    if not module:
        return json_resp ({"result": False, "msg": "module is required"}, status=400)
    
    LecturerContainter=get_lecturer_container()
    RoomContainer = get_lecture_container()

    #Simple query if the lecture exists
    lecturers=list(LecturerContainter.query_items(
        query="SELECT * FROM l WHERE l.name =@name",
        parameters=[{"name": "@name", "value": lecturer_name}],
        enable_cross_partition_query=True
    ))

    if not lecturers:
        return json_resp({"result": False, "msg": "lecturer not found"}, status=404)
    
    lecturer = lecturers[0]
    if module not in lecturer.get("modules", []):
        return json_resp(
            {"result": False, "msg": "lecturer does not teach this module", "allowed": lecturer.get("modules", [])},
            status=400
        )
    
    # Query to Get room docs or create if missing
    room_docs = list(RoomContainer.query_items(
        query="SELECT * FROM r WHERE r.roomId = @rid OR r.id = @rid",
        parameters=[{"name": "@rid", "value": room_id}],
        enable_cross_partition_query=True
    ))
    if room_docs:
        room = room_docs[0]
    else:
        room = {"id": room_id, "roomId": room_id, "status": "empty", "module": None, "lecturer": None, "startedAt": None}
        RoomContainer.create_item(body=room)
        room = list(RoomContainer.query_items(
            query="SELECT * FROM r WHERE r.id = @rid",
            parameters=[{"name": "@rid", "value": room_id}],
            enable_cross_partition_query=True
        ))[0]
    room["module"] = module

    RoomContainer.replace_item(item=room["id"], body=room)
    return json_resp(
        {"result": True, "msg": "module set", "room": room},
        status=200
    )

@app.route(route="lecture/setLecturer", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_set_lecturer(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/setLecturer")

    data, err = parse_json(req)
    if err:
        return err
    
    room_id = (data.get("roomId") or "").strip()
    lecturer_name = (data.get("lecturer") or "").strip()
    action = (data.get("action") or "").strip().lower()

    if not room_id:
        return json_resp({"result": False, "msg": "roomId is required"}, status=400)
    if not lecturer_name:
        return json_resp({"result": False, "msg": "lecturer is required"}, status=400)
    if action not in ("start", "end"):
        return json_resp({"result": False, "msg": "action must be 'start' or 'end'"}, status=400)
    
    LecturerContainer = get_lecturer_container()
    RoomContainer = get_lecture_container()

    # Query to check if the lecture exists
    lecturers = list(LecturerContainer.query_items(
        query="SELECT * FROM l WHERE l.name = @name",
        parameters=[{"name": "@name", "value": lecturer_name}],
        enable_cross_partition_query=True
    ))

    if not lecturers:
        return json_resp({"result": False, "msg": "lecturer not fond"}, status=404)
    
    # Query to Get room docs or create if missing
    room_docs = list(RoomContainer.query_items(
        query="SELECT * FROM r WHERE r.roomId = @rid OR r.id = @rid",
        parameters=[{"name": "@rid", "value": room_id}],
        enable_cross_partition_query=True
    ))
    if room_docs:
        room = room_docs[0]
    else:
        room = {"id": room_id, "roomId": room_id, "status": "empty", "module": None, "lecturer": None, "startedAt": None}
        RoomContainer.create_item(body=room)
        room = list(RoomContainer.query_items(
            query="SELECT * FROM r WHERE r.id = @rid",
            parameters=[{"name": "@rid", "value": room_id}],
            enable_cross_partition_query=True
        ))[0]
    
    
    # Other lecturer cannot take away another lecturers room
    if action == "start":
        if room.get("lecturer") and room["lecturer"] != lecturer_name:
            return json_resp({"result": False, "msg": "room already booked by another lecturer"}, status=409)
        
        room["lecturer"] = lecturer_name
        room["status"] = "booked"
        room["startedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        RoomContainer.replace_item(item=room["id"], body=room)
        return json_resp({"result": True, "msg": "lecturer set", "room": room}, status=200)
    
    #End
    else:
        if room.get("lecturer") != lecturer_name:
            return json_resp({"result": False, "msg": "you can only end your own lecture"}, status=403)
        
        room["lecturer"] = None
        room["status"] = "empty"
        room["startedAt"] = None
        RoomContainer.replace_item(item=room["id"], body=room)
        return json_resp({"result": True, "msg": "lecturer cleared", "room": room}, status=200)


# helpers for new lecture APIs
def clean_unique_modules(mods):
    if not isinstance(mods, list):
        return []
    cleaned = []
    seen = set()
    for m in mods:
        if isinstance(m, str):
            mm = m.strip()
            if mm and mm not in seen:
                seen.add(mm)
                cleaned.append(mm)
    return cleaned

def get_or_create_building_doc(building: str):
    LectureContainer = get_lecture_container()
    building = (building or "").strip()
    if not building:
        return None, json_resp({"result": False, "msg": "building is required"}, status=400)

    existing = list(LectureContainer.query_items(
        query="SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": building}],
        enable_cross_partition_query=True
    ))

    if existing:
        return existing[0], None

    doc = {
        "id": building,
        "building": building,
        "lecturer": None,
        "module": None,
        "students": []
    }
    LectureContainer.upsert_item(body=doc)
    return doc, None

# Student modules: get / replace
@app.route(route="student/modules/get", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
def student_modules_get(req: func.HttpRequest) -> func.HttpResponse:
    name = (req.params.get("name") or "").strip()
    if not name:
        return json_resp({"result": False, "msg": "name is required"}, status=400)

    StudentContainer = get_student_container()
    students = list(StudentContainer.query_items(
        query="SELECT * FROM s WHERE s.name = @name",
        parameters=[{"name": "@name", "value": name}],
        enable_cross_partition_query=True
    ))
    if not students:
        return json_resp({"result": False, "msg": "student not found"}, status=404)

    s = students[0]
    return json_resp({"result": True, "modules": s.get("modules", [])}, status=200)


@app.route(route="student/modules/replace", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def student_modules_replace(req: func.HttpRequest) -> func.HttpResponse:
    data, err = parse_json(req)
    if err:
        return err

    name = (data.get("name") or "").strip()
    modules = clean_unique_modules(data.get("modules") or [])

    if not name:
        return json_resp({"result": False, "msg": "name is required"}, status=400)

    if len(modules) != 4:
        return json_resp({"result": False, "msg": "students must have exactly 4 different modules"}, status=400)

    invalid = [m for m in modules if m not in ALLOWED_MODULES]
    if invalid:
        return json_resp({"result": False, "msg": "invalid module(s)", "invalid": invalid}, status=400)

    StudentContainer = get_student_container()
    students = list(StudentContainer.query_items(
        query="SELECT * FROM s WHERE s.name = @name",
        parameters=[{"name": "@name", "value": name}],
        enable_cross_partition_query=True
    ))
    if not students:
        return json_resp({"result": False, "msg": "student not found"}, status=404)

    s = students[0]
    s["modules"] = modules
    StudentContainer.replace_item(item=s["id"], body=s)

    return json_resp({"result": True, "msg": "OK", "modules": modules}, status=200)



@app.route(route="lecturer/modules/get", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
def lecturer_modules_get(req: func.HttpRequest) -> func.HttpResponse:
    name = (req.params.get("name") or "").strip()
    if not name:
        return json_resp({"result": False, "msg": "name is required"}, status=400)

    LecturerContainer = get_lecturer_container()
    lecturers = list(LecturerContainer.query_items(
        query="SELECT * FROM l WHERE l.name = @name",
        parameters=[{"name": "@name", "value": name}],
        enable_cross_partition_query=True
    ))
    if not lecturers:
        return json_resp({"result": False, "msg": "lecturer not found"}, status=404)

    l = lecturers[0]
    return json_resp({"result": True, "modules": l.get("modules", [])}, status=200)


@app.route(route="lecturer/modules/replace", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecturer_modules_replace(req: func.HttpRequest) -> func.HttpResponse:
    data, err = parse_json(req)
    if err:
        return err

    name = (data.get("name") or "").strip()
    modules = clean_unique_modules(data.get("modules") or [])

    if not name:
        return json_resp({"result": False, "msg": "name is required"}, status=400)

    if len(modules) != 3:
        return json_resp({"result": False, "msg": "lecturers must have exactly 3 different modules"}, status=400)

    invalid = [m for m in modules if m not in ALLOWED_MODULES]
    if invalid:
        return json_resp({"result": False, "msg": "invalid module(s)", "invalid": invalid}, status=400)

    LecturerContainer = get_lecturer_container()
    lecturers = list(LecturerContainer.query_items(
        query="SELECT * FROM l WHERE l.name = @name",
        parameters=[{"name": "@name", "value": name}],
        enable_cross_partition_query=True
    ))
    if not lecturers:
        return json_resp({"result": False, "msg": "lecturer not found"}, status=404)

    l = lecturers[0]
    l["modules"] = modules
    LecturerContainer.replace_item(item=l["id"], body=l)

    return json_resp({"result": True, "msg": "OK", "modules": modules}, status=200)


@app.route(route="lecture/student/add", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_student_add(req: func.HttpRequest) -> func.HttpResponse:
    data, err = parse_json(req)
    if err:
        return err

    building = (data.get("building") or "").strip()
    student = (data.get("student") or "").strip()

    if not building or not student:
        return json_resp({"result": False, "msg": "building and student are required"}, status=400)

    doc, derr = get_or_create_building_doc(building)

    if derr:
        return derr
    
    if not doc.get("lecturer"):
        return json_resp({"result": False, "msg": "no lecture running in this building"}, status=400)

    students = doc.get("students") or []
    if student not in students:
        students.append(student)

    doc["students"] = students
    get_lecture_container().upsert_item(body=doc)

    return json_resp({"result": True, "msg": "OK", "students": students}, status=200)

@app.route(route="lecture/student/remove", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_student_remove(req: func.HttpRequest) -> func.HttpResponse:
    data, err = parse_json(req)
    if err:
        return err

    building = (data.get("building") or "").strip()
    student = (data.get("student") or "").strip()

    if not building or not student:
        return json_resp({"result": False, "msg": "building and student are required"}, status=400)

    doc, derr = get_or_create_building_doc(building)
    if derr:
        return derr

    students = doc.get("students") or []
    doc["students"] = [s for s in students if s != student]

    get_lecture_container().upsert_item(body=doc)

    return json_resp({"result": True, "msg": "OK", "students": doc["students"]}, status=200)


@app.route(route="lecture/end", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_end(req: func.HttpRequest) -> func.HttpResponse:
    data, err = parse_json(req)
    if err:
        return err

    building = (data.get("building") or "").strip()
    if not building:
        return json_resp({"result": False, "msg": "building is required"}, status=400)

    doc, derr = get_or_create_building_doc(building)
    if derr:
        return derr

    # clear everything except building
    doc["lecturer"] = None
    doc["module"] = None
    doc["students"] = []

    get_lecture_container().upsert_item(body=doc)

    return json_resp({"result": True, "msg": "OK", "building": building}, status=200)