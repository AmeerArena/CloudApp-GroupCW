'use strict';

// Set up express
const express = require('express');
const app = express();

// Enable JSON body parsing
app.use(express.json());

// Setup socket.io
const server = require('http').Server(app);
const io = require('socket.io')(server);

// Setup static page handling
app.set('view engine', 'ejs');
app.use('/static', express.static('public'));

//Handle client interface on /
app.get('/', (req, res) => {
    res.render('client');
});

const BACKEND_ENDPOINT = process.env.BACKEND || 'https://groupcoursework-functionapp-2526.azurewebsites.net/api';

const FUNCTION_KEY = process.env.FUNCTION_KEY || 'hsuAcj6yIqFu2S-duKquK2DXhpg85E_BZjvxPqrC84HmAzFuo27TyQ==';


async function studentLogin(username, password) {
    try {
        console.log(`Logging in student: ${username}. Password: ${password}`);

        const response = await fetch(`${BACKEND_ENDPOINT}/student/login?code=${FUNCTION_KEY}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: username, password })
        });

        const data = await response.json();

        if (!data.result) {
            return { error: data.msg || "Login failed" };
        }

        return data;

    } catch (err) {
        console.error("Student login API ERROR:", err);
        return { error: "API_ERROR" };
    }
}

async function studentEnroll(name, password, modules) {
    try {
        const response = await fetch(
            `${BACKEND_ENDPOINT}/student/enroll?code=${FUNCTION_KEY}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, password, modules })
            }
        );

        const data = await response.json();

        if (!data.result) {
            return { error: data.msg || "Registration failed" };
        }

        return data;

    } catch (err) {
        console.error("Student enroll API ERROR:", err);
        return { error: "API_ERROR" };
    }
}

async function lecturerLogin(username, password) {
    try {
        console.log(`Logging in lecturer: ${username}`);

        const response = await fetch(`${BACKEND_ENDPOINT}/lecturer/login?code=${FUNCTION_KEY}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: username, password })
        });

        const data = await response.json();

        if (!data.result) {
            return { error: data.msg || "Login failed" };
        }

        return data;

    } catch (err) {
        console.error("Lecturer login API ERROR:", err);
        return { error: "API_ERROR" };
    }
}

async function lecturerHire(name, password, modules) {
    try {
        const response = await fetch(
            `${BACKEND_ENDPOINT}/lecturer/hire?code=${FUNCTION_KEY}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, password, modules })
            }
        );

        const data = await response.json();

        if (!data.result) {
            return { error: data.msg || "Registration failed" };
        }

        return data;

    } catch (err) {
        console.error("Lecturer hire API ERROR:", err);
        return { error: "API_ERROR" };
    }
}

// for lecture setup!
async function lectureSetup(lecturerId, roomId, module) {
    try {
        const moduleResponse = await fetch(`${BACKEND_ENDPOINT}/lecture/setModule?code=${FUNCTION_KEY}`, 
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ roomId, lecturer: lecturerId, module })
            });

        const moduleData = await moduleResponse.json();
        if (!moduleData.result) {
            return { error: moduleData.msg || "Set module failed" };
        }

        const lecturerResponse = await fetch(`${BACKEND_ENDPOINT}/lecture/setLecturer?code=${FUNCTION_KEY}`, 
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ roomId, lecturer: lecturerId, action: "start" })
            });

        const lecturerData = await lecturerResponse.json();
        if (!lecturerData.result) {
            return { error: lecturerData.msg || "Set lecturer failed" };
        }

        return lecturerData;

    } catch (err) {
        console.error("Lecture setup API ERROR:", err);
        return { error: "API_ERROR" };
    }
}


// Socket.io
io.on('connection', socket => {
    console.log('New connection');

    // Student Login
    socket.on('student:login', async (data) => {
        const { username, password } = data;

        const result = await studentLogin(username, password);

        if (result.error) {
            socket.emit('login:error', result.error);
            console.log(result.error);
            return;
        }

        // Successful login
        socket.emit('student:login:result', result);
        console.log('Student logged in:', result);
    });

    // Student Register
    socket.on('student:register', async (data) => {
        const { name, password, modules } = data;

        const result = await studentEnroll(name, password, modules);

        if (result.error) {
            socket.emit('register:error', result.error);
            return;
        }

        socket.emit('student:register:result', result);
    });

    // Lecturer Login
    socket.on('lecturer:login', async (data) => {
        const { username, password } = data;

        const result = await lecturerLogin(username, password);

        if (result.error) {
            socket.emit('lecturer:login:error', result.error);
            return;
        }

        socket.lecturerId = result.lecturer.id;
        socket.emit('lecturer:login:result', result);
        console.log('Lecturer logged in:', result);
    });

    // Lecturer Register
    socket.on('lecturer:register', async (data) => {
        const { name, password, modules } = data;
    
        const result = await lecturerHire(name, password, modules);
    
        if (result.error) {
            socket.emit('lecturer:register:error', result.error);
            return;
        }
    
        socket.emit('lecturer:register:result', result);
    });

    // Lecture Setup (please check this!!)
    socket.on('lecture:setup', async (data) => {
        const { roomId, module } = data;
        const lecturerId = socket.lecturerId;
        const result = await lectureSetup(lecturerId, roomId, module);

        if (result.error) {
            socket.emit('lecture:setup:error', result.error);
            return;
        }

        socket.emit('lecture:setup:result', result);

        // idk about this one...
        // console.log('Lecture setup successfully or something:', result);
    });

    socket.on('disconnect', () => console.log('Dropped connection'));
});


// Start server
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
    console.log(`Server listening on port ${PORT}`);
});

module.exports = server;
