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

# Gets the lecture container
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


# { "id": "string", "title": "string", "module": "string" } 
@app.route(route="lecture/setModule", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_set_module(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/setModule")

    data, err = parse_json(req)
    if err:
        return err

    lecture_id = (data.get("id") or "").strip()
    lecture_title = (data.get("title") or "").strip()
    lecture_module = (data.get("module") or "").strip()

    # Validate required fields
    if not lecture_id:
        return json_resp({"result": False, "msg": "id is required"}, status=400)

    if not lecture_title:
        return json_resp({"result": False, "msg": "title is required"}, status=400)

    if not lecture_module:
        return json_resp({"result": False, "msg": "module is required"}, status=400)

    # Validate module
    if lecture_module not in ALLOWED_MODULES:
        return json_resp(
            {
                "result": False,
                "msg": "invalid module",
                "allowed": sorted(ALLOWED_MODULES)
            },
            status=400
        )

    LectureContainer = get_lecture_container()

    # Get lecture by id (1-12)
    try:
        lecture = LectureContainer.read_item(
            item=lecture_id,
            partition_key=lecture_id
        )
    except Exception:
        return json_resp(
            {"result": False, "msg": "lecture not found"},
            status=404
        )

    lecture["title"] = lecture_title
    lecture["module"] = lecture_module

    LectureContainer.replace_item(
        item=lecture["id"],
        body=lecture
    )

    return json_resp(
        {"result": True, "msg": "lecture module updated"},
        status=200
    )

# { "id": "string", "lecturer": "string" , "date": "string", "time": "string" }
@app.route(route="lecture/setLecturer", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_set_lecturer(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/setLecturer")

    data, err = parse_json(req)
    if err:
        return err

    lecture_id = (data.get("id") or "").strip()
    lecture_lecturer = (data.get("lecturer") or "").strip()
    lecture_date = (data.get("date") or "").strip()   # YYYY-MM-DD
    lecture_time = (data.get("time") or "").strip()   # HH:MM

    # Validate required fields
    if not lecture_id:
        return json_resp({"result": False, "msg": "id is required"}, status=400)

    if not lecture_lecturer:
        return json_resp({"result": False, "msg": "lecturer is required"}, status=400)

    if not lecture_date:
        return json_resp({"result": False, "msg": "date is required"}, status=400)

    if not lecture_time:
        return json_resp({"result": False, "msg": "time is required"}, status=400)

    # Validate date format
    try:
        datetime.datetime.strptime(lecture_date, "%Y-%m-%d")
    except ValueError:
        return json_resp(
            {"result": False, "msg": "date format must be YYYY-MM-DD"},
            status=400
        )

    # Validate time format
    try:
        datetime.datetime.strptime(lecture_time, "%H:%M")
    except ValueError:
        return json_resp(
            {"result": False, "msg": "time format must be HH:MM"},
            status=400
        )

    LecturerContainer = get_lecturer_container()
    LectureContainer = get_lecture_container()

    # Check if lecturer exists
    lecturers = list(LecturerContainer.query_items(
        query="SELECT * FROM l WHERE l.name = @name",
        parameters=[{"name": "@name", "value": lecture_lecturer}],
        enable_cross_partition_query=True
    ))

    if not lecturers:
        return json_resp(
            {"result": False, "msg": "lecturer not found"},
            status=404
        )

    # Get lecture by id (1-12)
    try:
        lecture = LectureContainer.read_item(
            item=lecture_id,
            partition_key=lecture_id
        )
    except Exception:
        return json_resp(
            {"result": False, "msg": "lecture not found"},
            status=404
        )

    # Update
    lecture["lecturer"] = lecture_lecturer
    lecture["date"] = lecture_date
    lecture["time"] = lecture_time

    LectureContainer.replace_item(
        item=lecture["id"],
        body=lecture
    )

    return json_resp(
        {"result": True, "msg": "lecture updated"},
        status=200
    )

# {"id": "string", "student" : "string" }
@app.route(route="lecture/student/add", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_student_add(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/student/add")

    data, err = parse_json(req)
    if err:
        return err

    lecture_id = (data.get("id") or "").strip()
    student_name = (data.get("student") or "").strip()

    # Validate input
    if not lecture_id:
        return json_resp({"result": False, "msg": "id is required"}, status=400)

    if not student_name:
        return json_resp({"result": False, "msg": "student is required"}, status=400)

    LectureContainer = get_lecture_container()
    StudentContainer = get_student_container()

    # Check student exists
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

    # Get lecture by id (1-12)
    try:
        lecture = LectureContainer.read_item(
            item=lecture_id,
            partition_key=lecture_id
        )
    except Exception:
        return json_resp(
            {"result": False, "msg": "lecture not found"},
            status=404
        )

    # CHeck students list exists
    lecture_students = lecture.get("students") or []

    # No duplicates
    if student_name in lecture_students:
        return json_resp(
            {"result": False, "msg": "student already in lecture"},
            status=409
        )

    # Add student
    lecture_students.append(student_name)
    lecture["students"] = lecture_students

    LectureContainer.replace_item(
        item=lecture["id"],
        body=lecture
    )

    return json_resp(
        {"result": True, "msg": "student added to lecture"},
        status=200
    )

# { "id": "string", "studnt": "string" } 
@app.route(route="lecture/student/remove", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_student_remove(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/student/remove")

    data, err = parse_json(req)
    if err:
        return err

    lecture_id = (data.get("id") or "").strip()
    student_name = (data.get("student") or "").strip()

    # Validate input
    if not lecture_id:
        return json_resp({"result": False, "msg": "id is required"}, status=400)

    if not student_name:
        return json_resp({"result": False, "msg": "student is required"}, status=400)

    LectureContainer = get_lecture_container()

    # Get lecture by id (1-12)
    try:
        lecture = LectureContainer.read_item(
            item=lecture_id,
            partition_key=lecture_id
            
        )
    except Exception:
        return json_resp(
            {"result": False, "msg": "lecture not found"},
            status=404
        )

    lecture_students = lecture.get("students") or []

    if student_name not in lecture_students:
        return json_resp(
            {"result": False, "msg": "student not in lecture"},
            status=404
        )

    # Remove student
    lecture_students.remove(student_name)
    lecture["students"] = lecture_students

    LectureContainer.replace_item(
        item=lecture["id"],
        body=lecture
    )

    return json_resp(
        {"result": True, "msg": "student removed from lecture"},
        status=200
    )

# { "id": "string"} 
@app.route(route="lecture/end", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecture_end(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecture/end")

    data, err = parse_json(req)
    if err:
        return err

    lecture_id = (data.get("id") or "").strip()

    # Validate input
    if not lecture_id:
        return json_resp(
            {"result": False, "msg": "id is required"},
            status=400
        )

    LectureContainer = get_lecture_container()

    # Get lecture by id (1-12)
    try:
        lecture = LectureContainer.read_item(
            item=lecture_id,
            partition_key=lecture_id
        )
    except Exception:
        return json_resp(
            {"result": False, "msg": "lecture not found"},
            status=404
        )

    # Reset lecture
    lecture["title"] = ""
    lecture["module"] = ""
    lecture["lecturer"] = ""
    lecture["students"] = []
    lecture["date"] = ""
    lecture["time"] = ""


    LectureContainer.replace_item(
        item=lecture["id"],
        body=lecture
    )

    return json_resp(
        {"result": True, "msg": "lecture reset successfully"},
        status=200
    )


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
