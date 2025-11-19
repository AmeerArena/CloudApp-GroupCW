import azure.functions as func
import datetime
import json
import logging
import os
import uuid
from azure.cosmos import CosmosClient

app = func.FunctionApp()

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

# enroll a student. json: {"name":  "string" , "modules": ["module1","module2"]}
@app.route(route="student/enroll", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def student_enroll(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('student/enroll')

    try:
        data = req.get_json()
    except Exception as e:
        logging.error(e)
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "not a correct json"})
        )

    student_name = data.get("name", "") # student name
    student_modules = data.get("modules", []) # list of modules that the student is taking
    
    if not student_name:
        return func.HttpResponse(json.dumps({"result": False, "msg": "student must have a name"}))
    
    if len(student_modules) < 1 or len(student_modules) > 4:
        return func.HttpResponse(json.dumps({"result": False, "msg": "Student must take anywhere between 1 and 4 modules. "}))
    

    StudentContainer = get_student_container()
    
    students = list(StudentContainer.query_items(
        query = "SELECT * FROM s WHERE s.name = @name",
        parameters = [{"name": "@name", "value": student_name}],
        enable_cross_partition_query = True
    ))
    if len(students) > 0:
        return func.HttpResponse(
            json.dumps({"result": False, "msg": "student already exists"})
        )

    newStudent = {
        "id": str(uuid.uuid4()),
        "name": student_name,
        "modules": student_modules,
        "attended_lectures": []
    }

    StudentContainer.create_item(body = newStudent)
    
    logging.info('new student')
    return func.HttpResponse(
        json.dumps({"result": True, "msg": "OK"})
    )

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

@app.route(route="student/changesmodules", auth_level=func.AuthLevel.FUNCTION, methods=["PUT"])
def student_changesmodules(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Student change modules function running.')

    studentjson = req.get_json()
    student_name = studentjson.get("name")
    new_modules = studentjson.get("new_modules")

    if not student_name:
        return func.HttpResponse(json.dumps({"result": False, "msg": "Student must have a name"}))
    
    if not new_modules:
        return func.HttpResponse(json.dumps({"result": False, "msg": "No new module choice"}))
    
    studentContainer = get_student_container()

    students = list(
        studentContainer.query_items(
            query="SELECT * FROM s WHERE s.name = @name",
            parameters=[{"name": "@name", "value": student_name}],
            enable_cross_partition_query = True
        )
    )
    student = students[0]

    if not student:
        return func.HttpResponse(json.dumps({"result": False, "msg": "Student doesn't exist"}))
    
    if len(new_modules) < 1 or len(new_modules) > 4:
        return func.HttpResponse(json.dumps({"result": False, "msg": "New module selection must be anywehere between 1 to 4 modules"}))
    
    student["modules"] = new_modules
    studentContainer.replace_item(item = student["id"], body = student)
    
    return func.HttpResponse(json.dumps({"result": True, "msg": True}))








@app.route(route="student_attendlectures", auth_level=func.AuthLevel.FUNCTION)
def student_attendlectures(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )