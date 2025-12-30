import azure.functions as func
import datetime
import json
import logging
import os
import uuid
from azure.cosmos import CosmosClient

# Helpers
# Return JSON with propper content type and status code

def json_resp(payload: dict, status: int = 200) -> func.HttpResponse:
    return func.httpResponse(
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
    
#Validate date format YYYY-MM-DD ensure that it is not the past
# Return as (0k: bool, error_response: HttpResponse(None))
def validate_data (date_str: str):
    if not isinstance(date_str, str) or not date_str.strip():
        return False, json_resp({"result": False, "msg": "date is required"}, status=400)
    
    try:
        requested = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False, json_resp({"result": False, "msg": "date format must be YYYY-MM-DD"}, status=400)
    
    today = datetime.now(datetime.timezone.utc)

    if requested < today:
        return False, json_resp({"result": False, "msg": "cannot book a date in the past"}, status=400)
    
app = func.FunctionApp()

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

# Gets the lecturer container -- Remove
def get_lecturer_container():
    db = get_cosmos_db()
    lecturer_container_name = os.environ.get("LecturerContainerName", "lecturer")
    return db.get_container_client(lecturer_container_name)

# Gets the student container
def get_student_container():
    db = get_cosmos_db()
    student_container_name = os.environ.get("StudentContainerName", "student")
    return db.get_container_client(student_container_name)

# enroll a student. json: {"name":  "string" , "modules": ["module1","module2"]}
@app.route(route="student/enroll", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def student_enroll(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('student/enroll')

    data, err = parse_json(req)
    if err:
        return err

    student_name = (data.get("name") or " ").strip()
    student_modules = data.get("modules") or []

    # validate student name
    if not student_name:
        return json_resp({"result": False, "msg": "student must have a name"}, status=400)

    # Validate student modules list
    if not isinstance(student_modules, list) or len(student_modules) == 0:
        return json_resp(
            {"result": False, "msg": "student must take at least 1 module"},
            status=400
        )
    
    #Clean and remove dupes module list
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
            {"results": False, "msg": "modules must be valid strings"},
            status=400
        )
    
    StudentContainer = get_student_container()

     # Checking if student exists
    students = list(StudentContainer.query_items(
        query= "SELECT * FROM s WHERE s.name =@name",
        parameters=[{"name": "@name", "value": student_name}],
        enable_cross_partition_query=True
    ))

    if students:
        return json_resp(
        {"result": False, "msg": "student already exists"},
        status=409
    )

    #  Create new student document
    newStudent = {
        "id": str(uuid.uuid4()),
        "name": cleaned_modules,
        "lecturer_name": data.get("lecturer_name", "") #Optional, links lectuerer for student view
    }

    StudentContainer.create_item(body=newStudent)
    return json_resp({"result": True, "msg": "OK"}, status=201)


#Lecturer login
# Login only if lecturer exists
# JSON body example: { "name": "Dr. Alwash"}
@app.route(route="lecturer/login", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecturer_login(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("lecturer/login")
    data, err = parse_json(req)

    if err:
        return err
    
    lecturer_name = (data.get("name") or "").strip()
    if not lecturer_name:
        return json_resp(
            {"result": False, "msg": "name is required"},
            status=400
        )
    
    LecturerContainer = get_lecturer_container()

    lecturers = list(LecturerContainer.query_items(
        query = "SELECT FROM 1 WHERE 1.name = @name",
        parameters=[{"name": "@name", "value": lecturer_name}],
        enable_cross_partition_query=True
    ))

    if not lecturers:
        return json_resp(
            {"result": False, "msg": "lecturer not found"},
            status=404
        )
    
    lecturer = lecturers[0]

    #Ensuring booking array exists for grid
    if "bookings" not in lecturer:
        lecturer["bookings"] = []
        LecturerContainer.replace_item(
            item=lecturer["id"],
            body=lecturer
        )
    
    return json_resp({
        "result": True,
        "msg": "OK",
        "lecturer": {
            "id": lecturer.get("id"),
            "name": lecturer.get("name"),
            "modules": lecturer.get("modules", [])
        }
    })


#Student login
#Student allowed to login only if they exist
#Example JSON body: { "name": "Aarfa"}
@app.route(route="student/login", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def student_login(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("student/login")
    data, err = parse_json(req)
    if err:
        return err
    


    student_name = (data.get("name") or "").strip()
    if not student_name:
        return json_resp(
            {"result": False, "msg": "name is required"},
            status=400
        )

    StudentContainer = get_student_container()

    students = list(StudentContainer.quey_items(
        query="SELECT * FROM s WHERE s.name = @name",
        parameter=[{"name": "@name", "value": student_name}],
        enable_cross_partition_query=True
    ))

    if not students:
        return json_resp(
            {"result": False, "msg": "student not found"},
            status=404
        )
    
    student = students[0]

    return json_resp({
        "result": True,
        "msg": "OK",
        "student": {
            "id": student.get("id"),
            "name": student.get("name"),
            "modules": student.get("modules", []),
            "lecturer_name": student.get("lecturer_name", "")
        }
    })


# hire a lecturer. json: {"name":  "string" , "modules": ["module1","module2"]}
@app.route(route="lecturer/hire", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def lecturer_hire(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('lecturer/hire')

    try:
        data = req.get_json()
    except Exception as e:
        logging.error(e)
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "not a correct json"})
        )

    lecturer_name = data.get("name", "") # lecturer name
    lecturer_modules = data.get("modules", []) # list of modules that the lecturer teaches
    
    if not lecturer_name:
        return func.HttpResponse(json.dumps({"result": False, "msg": "lecturer must have a name"}))
    
    if not lecturer_modules:
        return func.HttpResponse(json.dumps({"result": False, "msg": "lecturer must teach at least 1 module"}))

    LecturerContainer = get_lecturer_container()
    
    lecturers = list(LecturerContainer.query_items(
        query = "SELECT * FROM l WHERE l.name = @name",
        parameters = [{"name": "@name", "value": lecturer_name}],
        enable_cross_partition_query = True
    ))
    if len(lecturers) > 0:
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "lecturer already exists"})
        )

    newLecturer = {
        "id": str(uuid.uuid4()),
        "name": lecturer_name,
        "modules": lecturer_modules,
        "lectures": []
    }

    LecturerContainer.create_item(body = newLecturer)
    
    logging.info('new lecturer')
    return func.HttpResponse(
        json.dumps({"result": True, "msg": "OK"})
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

#Done:
# Students can be enrolled w/ names and modules
# Student can login 
# Lecturers "" ""
# All resuponses return a clean JSON body
# Invalid requests are rejected safeley
# Dates in the past cannot be booked
# Lecture databases exists but not used

#TODO:
#Get lecturer grid status (2 * 3 slots)
# Grey = Empty, Red = booked by another lecturer, Green = Booked by current lecturer
# Lecturer select slot (book room + time)
# Prevent double booking of same slot
# Lecturer cancel booking (uselect slot)
# Student view lecturers booking for a given date

# NOTE:
# No lecture data is written to the lecture container
# All booking data will be stored on lecturer records
