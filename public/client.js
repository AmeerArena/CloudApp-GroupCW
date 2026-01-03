var socket = null;

var app = new Vue({
    el: '#client',
    data: {
        connected: false,

        // login
        me: null,
        loginName: '',
        loginPassword: '',
        loginError: '',

        // page state
        page: 'login',

        // student register
        registerName: '',
        registerPassword: '',
        registerModules: ['', '', '', ''],
        registerError: '',

        lecturerRegisterName: '',
        lecturerRegisterPassword: '',
        lecturerRegisterModules: ['', '', ''],
        lecturerRegisterError: '',

        modules: [
            "BIOM1","BIOM2","BIOM3",
            "COMP1","COMP2","COMP3",
            "ELEC1","ELEC2","ELEC3",
            "MATH1","MATH2","MATH3"
        ]
    },
    mounted() {
        connect();
    },
    methods: {
        loginStudent() {
            this.loginError = '';

            if (!socket || !this.connected) {
                this.loginError = 'Not connected to server';
                return;
            }

            socket.emit('student:login', {
                username: this.loginName,
                password: this.loginPassword
            });
        },

        loginLecturer() {
            this.loginError = '';

            if (!socket || !this.connected) {
                this.loginError = 'Not connected to server';
                return;
            }
        
            socket.emit('lecturer:login', {
                username: this.loginName,
                password: this.loginPassword
            });
        },

        goToRegister() {
            this.page = 'register';
        },

        goToLecturerRegister() {
            this.page = 'registerLecturer';
            this.registerError = '';
        },

        goToLogin() {
            this.page = 'login';
            this.registerError = '';
        },

        registerStudent() {
            this.registerError = '';

            const modules = this.registerModules.filter(Boolean);

            socket.emit('student:register', {
                name: this.registerName,
                password: this.registerPassword,
                modules
            });
        },

        registerLecturer() {
            this.lecturerRegisterError = '';

            const modules = this.lecturerRegisterModules.filter(Boolean);

            socket.emit('lecturer:register', {
                name: this.lecturerRegisterName,
                password: this.lecturerRegisterPassword,
                modules
            });
        }
    }
});

function connect() {
    if (socket) return;

    socket = io();

    socket.on('connect', function () {
        console.log('Socket connected');
        app.connected = true;
    });

    // Login student
    socket.on('login:error', (msg) => {
        app.loginError = msg;
    });

    socket.on('student:login:result', (data) => {
        console.log('LOGIN RESULT:', data);
        app.me = data.student || data;
    });

    // Login lecturer
    socket.on('lecturer:login:error', (msg) => {
        app.loginError = msg;
    });

    socket.on('lecturer:login:result', (data) => {
        console.log('LECTURER LOGIN RESULT:', data);
        app.me = data.lecturer || data;
    });

    // Register student
    socket.on('register:error', (msg) => {
        app.registerError = msg;
    });
    
    socket.on('student:register:result', () => {
        app.page = 'login';
        app.registerName = '';
        app.registerPassword = '';
        app.registerModules = ['', '', '', ''];
    });

    // Register lecturer
    socket.on('lecturer:register:error', (msg) => {
        app.lecturerRegisterError = msg;
    });
    
    socket.on('lecturer:register:result', () => {
        app.page = 'login';
        app.lecturerRegisterName = '';
        app.lecturerRegisterPassword = '';
        app.lecturerRegisterModules = ['', '', ''];
    });

    socket.on('disconnect', function () {
        console.log('Socket disconnected');
        app.connected = false;
        socket = null;
    });
}

