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
        ],

        // lecture setup
        roomId: '',
        selectedModule: '',
        setupError: '',
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
        },

        setupLecture() {
            this.setupError = '';
            if (!socket || !this.connected) {
                this.setupError = 'Not connected to server';
                return;
            }
            socket.emit('lecture:setup', {
                roomId: this.roomId,
                module: this.selectedModule
            });
        },

        // someone please check this!! I made this to be the main page after logging in (home page?)
        goToMain() {
            this.page = 'main';
            this.roomId = '';
            this.selectedModule = '';
            this.setupError = '';
        },

        // idk...
        logout() {
            this.me = null;
            this.page = 'login';
            this.loginName = '';
            this.loginPassword = '';
            this.loginError = '';
            this.registerName = '';
            this.registerPassword = '';
            this.registerModules = ['', '', '', ''];
            this.registerError = '';
            this.lecturerRegisterName = '';
            this.lecturerRegisterPassword = '';
            this.lecturerRegisterModules = ['', '', ''];
            this.lecturerRegisterError = '';
            this.roomId = '';
            this.selectedModule = '';
            this.setupError = '';
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
        app.goToMain();
    });

    // Login lecturer
    socket.on('lecturer:login:error', (msg) => {
        app.loginError = msg;
    });

    socket.on('lecturer:login:result', (data) => {
        console.log('LECTURER LOGIN RESULT:', data);
        app.me = data.lecturer || data;
        app.goToMain();
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

    // Lecture setup
    socket.on('lecture:setup:result', (data) => {
        console.log('Lecture setup result:', data);
        app.page = 'main';
    });

    socket.on('lecture:setup:error', (msg) => {
        app.setupError = msg;
    });

    socket.on('disconnect', function () {
        console.log('Socket disconnected');
        app.connected = false;
        socket = null;
    });
}