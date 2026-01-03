'use strict';

// Set up express
const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();
app.use(express.urlencoded({ extended: true }));

// Enable JSON body parsing
app.use(express.json());

// Setup static page handling
app.set('view engine', 'ejs');
app.use('/static', express.static('public'));

// Setup socket.io
const server = require('http').Server(app);
const io = require('socket.io')(server);

app.get('/', (req, res) => res.redirect('/login'));
app.get('/login', (req, res) => res.render('login', { error: null }));
app.get('/register/student', (req, res) => res.render('register-student', { error: null }));
app.get('/register/lecturer', (req, res) => res.render('register-lecturer', { error: null }));
app.get('/homepage', (req, res) => res.render('homepage'));
app.get('/lecture-setup', (req, res) => res.render('lecture-setup', { error: null }));
app.get('/lecture', (req, res) => res.render('lecture'));
app.get('/student-enroll', (req, res) => res.render('student-enroll'));


const BACKEND_ENDPOINT = process.env.BACKEND || 'https://groupcoursework-functionapp-2526.azurewebsites.net/api';

const FUNCTION_KEY = process.env.FUNCTION_KEY || 'hsuAcj6yIqFu2S-duKquK2DXhpg85E_BZjvxPqrC84HmAzFuo27TyQ==';

// Helper to call Azure Functions
async function callFunction(route, payload) {
  const url = `${BACKEND_ENDPOINT}/${route}?code=${FUNCTION_KEY}`;
  const response = await axios.post(url, payload, { headers: { 'Content-Type': 'application/json' } });
  return response.data;
}

function parseModules(modulesRaw) {
  if (Array.isArray(modulesRaw)) return modulesRaw;
  if (typeof modulesRaw !== 'string') return [];
  return modulesRaw.split(',').map(m => m.trim()).filter(Boolean);
}

//student enroll (must send name+ password+modules)
app.post('/api/student/enroll', async (req, res) => {
  try {
    const result = await callFunction('student/enroll', {
      name: req.body.name,
      password: req.body.password,       
      modules: parseModules(req.body.modules)
    });
    return res.json(result);
  } catch (err) {
    console.error('Enroll error:', err.response?.status, err.response?.data || err.message);
    return res.status(500).json({ result: false, msg: 'Backend request failed' });
  }
});

// Lecturer hire (must send name,password, modules)
app.post('/api/lecturer/hire', async (req, res) => {
  try {
    const result = await callFunction('lecturer/hire', {
      name: req.body.name,
      password: req.body.password,       
      modules: parseModules(req.body.modules)
    });
    return res.json(result);
  } catch (err) {
    console.error('Hire error:', err.response?.status, err.response?.data || err.message);
    return res.status(500).json({ result: false, msg: 'Backend request failed' });
  }
});


 // Lecture make (must send title/module/lecturer/date/time)
app.post('/api/lecture/make', async (req, res) => {
  try {
    const result = await callFunction('lecture/make', {
      title: req.body.title,
      module: req.body.module,
      lecturer: req.body.lecturer,
      date: req.body.date,
      time: req.body.time
    });
    return res.json(result);
  } catch (err) {
    console.error('Make lecture error:', err.response?.status, err.response?.data || err.message);
    return res.status(500).json({ result: false, msg: 'Backend request failed' });
  }
});


// Socket.io
io.on('connection', socket => {
  console.log('New connection');
  socket.on('disconnect', () => console.log('Dropped connection'));
});

// Start server
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});

module.exports = server;
