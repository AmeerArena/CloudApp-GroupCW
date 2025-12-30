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
  res.render('student-enroll');
});
//Handle display interface on /display
app.get('/display', (req, res) => {
  res.render('display');
});

const axios = require('axios');

const BACKEND_ENDPOINT = process.env.BACKEND || 'https://groupcoursework-functionapp-2526.azurewebsites.net/api';

const FUNCTION_KEY = process.env.FUNCTION_KEY || 'hsuAcj6yIqFu2S-duKquK2DXhpg85E_BZjvxPqrC84HmAzFuo27TyQ==';

// Helper to call Azure Functions
async function callFunction(route, payload) {
  const url = `${BACKEND_ENDPOINT}/${route}?code=${FUNCTION_KEY}`;

  const response = await axios.post(url, payload, {
    headers: {
      'Content-Type': 'application/json'
    }
  });

  return response.data;
}


// student enroll
app.post('/api/student/enroll', async (req, res) => {
  try {
    const result = await callFunction('student/enroll', {
      name: req.body.name,
      modules: req.body.modules
    });

    res.json(result);
  } catch (err) {
    if (err.response) {
      console.error('Status:', err.response.status);
      console.error('Headers:', err.response.headers);
      console.error('Body:', err.response.data);
    } else {
      console.error('Request error:', err.message);
    }
  
    res.status(500).json({
      result: false,
      msg: 'Backend request failed'
    });
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
