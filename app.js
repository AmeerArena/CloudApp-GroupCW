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

const lectureParticipants = {};

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

async function startLectureFixed(lectureId, title, module, lecturer) {
    try {
        // Set module + title
        const modRes = await fetch(
            `${BACKEND_ENDPOINT}/lecture/setModule?code=${FUNCTION_KEY}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id: String(lectureId),
                    title: title,
                    module: module
                })
            }
        );

        const modData = await modRes.json();
        if (!modData.result) {
            return { error: modData.msg || "Failed to set module" };
        }

        // Set lecturer + date/time
        const now = new Date();
        const date = now.toISOString().split("T")[0];
        const time = now.toTimeString().substring(0, 5);

        const lecRes = await fetch(
            `${BACKEND_ENDPOINT}/lecture/setLecturer?code=${FUNCTION_KEY}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id: String(lectureId),
                    lecturer: lecturer,
                    date: date,
                    time: time
                })
            }
        );

        const lecData = await lecRes.json();
        if (!lecData.result) {
            return { error: lecData.msg || "Failed to set lecturer" };
        }

        return { result: true };

    } catch (err) {
        console.error("startLectureFixed ERROR:", err);
        return { error: "API_ERROR" };
    }
}

async function endLectureFixed(lectureId) {
    try {
        const response = await fetch(
            `${BACKEND_ENDPOINT}/lecture/end?code=${FUNCTION_KEY}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: String(lectureId) })
            }
        );

        const data = await response.json();
        if (!data.result) {
            return { error: data.msg || "Failed to end lecture" };
        }

        return data;
    } catch (err) {
        console.error("endLectureFixed ERROR:", err);
        return { error: "API_ERROR" };
    }
}

async function updateUserModules(userId, modules, isLecturer) {
    try {
        // Note: This endpoint may need to be created in the backend
        // For now, we'll use a placeholder approach
        // You may need to create an endpoint like /student/update or /lecturer/update
        
        const endpoint = isLecturer 
            ? `${BACKEND_ENDPOINT}/lecturer/update?code=${FUNCTION_KEY}`
            : `${BACKEND_ENDPOINT}/student/update?code=${FUNCTION_KEY}`;

        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                id: userId,
                modules: modules
            })
        });

        const data = await response.json();

        if (!data.result) {
            return { error: data.msg || "Failed to update modules" };
        }

        return data;

    } catch (err) {
        console.error("Update modules API ERROR:", err);
        // Return true for the time being
        return { result: true, modules: modules };
    }
}


// Store lecture data (board content and chat messages)
const lectureData = {};

// Socket.io
io.on('connection', socket => {
    console.log('New connection');
    let currentLecture = null;

    // Student Login
    socket.on('student:login', async (data) => {
        const { username, password } = data;

        const result = await studentLogin(username, password);

        if (result.error) {
            socket.emit('login:error', result.error);
            console.log(result.error);
            return;
        }

        // Store user name for chat
        socket.userName = result.student?.name || result.name || username;
        
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

        // Store user name for chat
        socket.userName = result.lecturer?.name || result.name || username;
        
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

    // Start Lecture
    socket.on('lecture:start', async (data) => {
        const { title, module, lecturer, building } = data;

        const lectureId = building; // building = lecture ID (1–12)

        const result = await startLectureFixed(
            lectureId,
            title,
            module,
            lecturer
        );

        if (result.error) {
            socket.emit('lecture:start:error', result.error);
            return;
        }

        // Store lecture locally
        lectureData[lectureId] = {
            boardContent: '',
            chatMessages: []
        };

        // Broadcast building update
        io.emit('lecture:building:update', {
            building: lectureId,
            lecture: {
                id: lectureId,
                title,
                module,
                lecturer
            }
        });

        socket.emit('lecture:start:result', {
            success: true,
            lectureId: lectureId
        });
    });

    // Join Lecture
    socket.on('lecture:join', (data) => {
        const { lectureTitle, userType } = data;
        currentLecture = lectureTitle;

        // Initialise if not exists
        if (!lectureData[lectureTitle]) {
            lectureData[lectureTitle] = {
                boardContent: '',
                chatMessages: []
            };
        }
        
        if (!lectureParticipants[lectureTitle]) {
            lectureParticipants[lectureTitle] = {};
        }

        lectureParticipants[lectureTitle][socket.id] = {
            userType: userType || "student",
            userName: socket.userName || "Anonymous"
        };

        const participants = Object.values(lectureParticipants[lectureTitle]);
        const studentCount = participants.filter(p => p.userType !== "lecturer").length;

        // Notify all clients about updated participant list
        io.emit('lecture:count:update', {
            lectureTitle,
            studentCount
        });

        // Send current board content and chat messages to the user
        socket.emit('board:update', {
            content: lectureData[lectureTitle].boardContent,
            lectureTitle: lectureTitle
        });

        // Send chat history
        lectureData[lectureTitle].chatMessages.forEach(msg => {
            socket.emit('chat:message', {
                user: msg.user,
                message: msg.message,
                time: msg.time,
                lectureTitle: lectureTitle
            });
        });
    });

    socket.on('lecture:end', async (lectureId) => {
        await endLectureFixed(lectureId);
        
        // Notify all clients
        io.emit('lecture:ended', {
            lectureId: lectureId
        });
    
        delete lectureData[lectureId];
        delete lectureParticipants[lectureId];
    });

    // Board Updates
    socket.on('board:update', (data) => {
        const { content, lectureTitle } = data;

        if (lectureTitle && lectureData[lectureTitle]) {
            lectureData[lectureTitle].boardContent = content;
            
            // Broadcast to all clients in this lecture
            io.emit('board:update', {
                content: content,
                lectureTitle: lectureTitle
            });
        }
    });

    // Chat Messages
    socket.on('chat:message', (data) => {
        const { message, lectureTitle } = data;
        
        if (lectureTitle && lectureData[lectureTitle]) {
            const chatMessage = {
                user: socket.userName || 'Anonymous',
                message: message,
                time: new Date().toLocaleTimeString()
            };

            lectureData[lectureTitle].chatMessages.push(chatMessage);

            // Broadcast to all clients in this lecture
            io.emit('chat:message', {
                user: chatMessage.user,
                message: chatMessage.message,
                time: chatMessage.time,
                lectureTitle: lectureTitle
            });
        }
    });

    // Store user name - will be set when login events are handled
    // This is handled in the login result handlers below

    // Update Modules
    socket.on('modules:update', async (data) => {
        const { modules, userId, isLecturer } = data;

        const result = await updateUserModules(userId, modules, isLecturer);

        if (result.error) {
            socket.emit('modules:update:error', result.error);
            return;
        }

        socket.emit('modules:update:result', {
            modules: modules,
            success: true
        });
    });

    socket.on('disconnect', () => {
        console.log('Dropped connection');
        
        if (currentLecture && lectureParticipants[currentLecture]) {
            delete lectureParticipants[currentLecture][socket.id];
        }
    
        currentLecture = null;
    });
});


// Start server
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});

module.exports = server;
