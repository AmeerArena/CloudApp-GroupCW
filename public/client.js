var socket = null;

// Prepare client
var app = new Vue({
    el: '#client',
    data: {
        connected: false,
        // Student enroll data
        studentName: '',
        studentPassword: '',
        studentModules: '',
        enrollResult: ''
    },
    mounted: function() {
        connect();
    },
    methods: {
        // enroll student
        enrollStudent() {
            if (!this.studentName || !this.studentPassword || !this.studentModules) {
                this.enrollResult = 'Please fill in all fields';
                return;
            }

            const modules = this.studentModules
                .split(',')
                .map(m => m.trim())
                .filter(m => m.length > 0);

            fetch('/api/student/enroll', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: this.studentName,
                    password: this.studentPassword,
                    modules: modules
                })
            })
            .then(res => res.json())
            .then(data => {
                this.enrollResult = data.msg;
                if (data.result) {
                    this.studentName = '';
                    this.studentPassword = '';
                    this.studentModules = '';
                }
            })
            .catch(() => {
                this.enrollResult = 'Server error';
            });
        }
    }
});

function connect() {
    // Prepare web socket
    socket = io();

    socket.on('connect', function() {
        app.connected = true;
    });

    socket.on('connect_error', function(message) {
        alert('Unable to connect: ' + message);
    });

    socket.on('disconnect', function() {
        alert('Disconnected');
        app.connected = false;
    });
}
