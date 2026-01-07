var socket = null;

var app = new Vue({
    el: '#client',
    data: {
        connected: false,

        // login
        me: null,
        userType: null, // 'lecturer' or 'student'
        loginName: '',
        loginPassword: '',
        loginError: '',

        // student or lecturer
        role: null,               
        selectedBuilding: null,
        buildings: Array.from({ length: 12 }, (_, i) => `Building-${String(i + 1).padStart(2, "0")}`),

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

        // Homepage: building selection and quick lecture start
        selectedBuilding: null, // Currently selected building number
        buildingLectures: {}, // Tracks which buildings have active lectures
        showStartLectureModal: false, // Controls modal visibility for quick start - a litte pop-up window that shows up
        quickLectureTitle: '', // Lecture title from homepage modal
        quickSelectedModule: '', // Module selection from homepage modal
        quickLectureError: '', // Error messages for homepage lecture start

        // lecture setup
        lectureTitle: '',
        selectedModule: '',
        lectureError: '',

        studentCount: 0,
        currentLectureModule: '',

        // in-lecture page
        currentLectureTitle: '',
        boardContent: '',
        chatMessages: [],
        chatInput: '',
        boardUpdateTimeout: null, // For debouncing board updates

        // settings
        updatedModules: [],
        settingsError: '',
        settingsSuccess: '',

        modules: [
            "BIOM1","BIOM2","BIOM3",
            "COMP1","COMP2","COMP3",
            "ELEC1","ELEC2","ELEC3",
            "MATH1","MATH2","MATH3"
        ]
    },
    computed: {
        lecturerModules() {
            if (this.me && this.me.modules) {
                return this.me.modules;
            }
            return [];
        },
        isLecturer() {
            return this.userType === 'lecturer';
        },
        canUpdateModules() {
            if (this.isLecturer) {
                return this.updatedModules.filter(Boolean).length === 3;
            } else {
                return this.updatedModules.filter(Boolean).length === 4;
            }
        }
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

        selectBuilding(buildingNumber) {
            // Select a building and close any open modals
            this.selectedBuilding = buildingNumber;
            this.showStartLectureModal = false;
        },

        goToLectureSetup() {
            if (!this.selectedBuilding) {
                alert('Please select a building first');
                return;
            }
            this.page = 'lectureSetup';
            this.lectureTitle = '';
            this.selectedModule = '';
            this.lectureError = '';
        },

        startLectureFromHomepage() {
            // Start lecture directly from homepage modal (quick start)
            this.quickLectureError = '';

            if (!this.quickLectureTitle || !this.quickSelectedModule) {
                this.quickLectureError = 'Please fill in all fields';
                return;
            }

            if (!this.selectedBuilding) {
                this.quickLectureError = 'Please select a building';
                return;
            }

            if (!socket || !this.connected) {
                this.quickLectureError = 'Not connected to server';
                return;
            }

            // Store lecture details and emit to server
            this.currentLectureTitle = this.quickLectureTitle;
            this.selectedModule = this.quickSelectedModule;
            socket.emit('lecture:start', {
                title: this.quickLectureTitle,
                module: this.quickSelectedModule,
                lecturer: this.me.name,
                building: this.selectedBuilding
            });

            // Close modal and clear form
            this.showStartLectureModal = false;
            this.quickLectureTitle = '';
            this.quickSelectedModule = '';
        },

        hasLectureInBuilding(buildingNumber) {
            // Check if building has an active lecture
            return this.buildingLectures[buildingNumber] !== undefined;
        },

        attendLecture() {
            // Student joins lecture in selected building
            if (!this.selectedBuilding || !this.hasLectureInBuilding(this.selectedBuilding)) {
                return;
            }
            const lecture = this.buildingLectures[this.selectedBuilding];
            this.currentLectureTitle = lecture.title || `Lecture in Building ${this.selectedBuilding}`;
            this.currentLectureModule = lecture.module || '';
            this.page = 'inLecture';
            if (socket) {
                socket.emit('lecture:join', { lectureTitle: this.currentLectureTitle, userType: this.userType });
            }
        },

        goBack() {
            if (this.page === 'settings') {
                // Go back to homepage
                this.page = 'homepage';
            } else if (this.page === 'lectureSetup') {
                // Go back to homepage from lecture setup
                this.page = 'homepage';
                this.lectureTitle = '';
                this.selectedModule = '';
                this.lectureError = '';
            } else {
                // Reset form and stay on current page
                this.lectureTitle = '';
                this.selectedModule = '';
                this.lectureError = '';
            }
        },

        startLecture() {
            // Start lecture from lecture setup page (includes building info)
            this.lectureError = '';

            if (!this.lectureTitle || !this.selectedModule) {
                this.lectureError = 'Please fill in all fields';
                return;
            }

            if (!this.selectedBuilding) {
                this.lectureError = 'Please select a building from the homepage';
                return;
            }

            if (!socket || !this.connected) {
                this.lectureError = 'Not connected to server';
                return;
            }

            this.currentLectureTitle = this.lectureTitle;
            socket.emit('lecture:start', {
                title: this.lectureTitle,
                module: this.selectedModule,
                lecturer: this.me.name,
                building: this.selectedBuilding
            });
        },

        updateBoard(event) {
            if (!socket || !this.connected) return;
            
            const content = event.target.innerHTML || event.target.innerText;
            
            // Update local content
            this.boardContent = content;
            
            // Debounce the socket emit to avoid too many updates
            if (this.boardUpdateTimeout) {
                clearTimeout(this.boardUpdateTimeout);
            }
            
            this.boardUpdateTimeout = setTimeout(() => {
                // Emit board update to server
                socket.emit('board:update', {
                    content: content,
                    lectureTitle: this.currentLectureTitle
                });
            }, 300); // Wait 300ms after user stops typing
        },

        sendMessage() {
            if (!this.chatInput.trim() || !socket || !this.connected) return;

            const message = {
                user: this.me.name,
                message: this.chatInput.trim(),
                time: new Date().toLocaleTimeString()
            };

            socket.emit('chat:message', {
                message: message.message,
                lectureTitle: this.currentLectureTitle
            });

            this.chatInput = '';
        },

        exitLecture() {
            if (this.isLecturer) {
                this.page = 'lectureSetup';
            } else {
                this.page = 'dashboard';
            }
            this.currentLectureTitle = '';
            this.boardContent = '';
            this.chatMessages = [];
            this.chatInput = '';
        },

        goToSettings() {
            this.page = 'settings';
            // Initialize updatedModules with current modules
            if (this.me && this.me.modules) {
                this.updatedModules = [...this.me.modules];
                // Pad with empty strings if needed
                if (this.isLecturer && this.updatedModules.length < 3) {
                    while (this.updatedModules.length < 3) {
                        this.updatedModules.push('');
                    }
                } else if (!this.isLecturer && this.updatedModules.length < 4) {
                    while (this.updatedModules.length < 4) {
                        this.updatedModules.push('');
                    }
                }
            } else {
                this.updatedModules = this.isLecturer ? ['', '', ''] : ['', '', '', ''];
            }
            this.settingsError = '';
            this.settingsSuccess = '';
        },

        updateModules() {
            this.settingsError = '';
            this.settingsSuccess = '';

            const modules = this.updatedModules.filter(Boolean);

            if (this.isLecturer && modules.length !== 3) {
                this.settingsError = 'Lecturers must have exactly 3 modules';
                return;
            }

            if (!this.isLecturer && modules.length !== 4) {
                this.settingsError = 'Students must have exactly 4 modules';
                return;
            }

            if (!socket || !this.connected) {
                this.settingsError = 'Not connected to server';
                return;
            }

            socket.emit('modules:update', {
                modules: modules,
                userId: this.me.id || this.me.name,
                isLecturer: this.isLecturer
            });
        }
    }
});

function updateUserDisplay() {
    const x = document.getElementById("userDisplay");
    if (!x) return;

    if (app.me && app.me.name && app.userType){
        x.style.display ="block";
        x.textContent = `Logged in as: ${app.me.name} (${app.userType})`;
    } else {
        x.style.displat = "none";
    }
}

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
        // Student login: navigate to homepage for building selection
        console.log('LOGIN RESULT:', data);
        app.me = data.student || data;
        app.userType = 'student';
        app.page = 'homepage';
        app.selectedBuilding = null;
        if (socket) {
            socket.userName = app.me.name;
        }
        updateUserDisplay();
    });

    // Login lecturer
    socket.on('lecturer:login:error', (msg) => {
        app.loginError = msg;
    });

    socket.on('lecturer:login:result', (data) => {
        // Lecturer login: navigate to homepage for building selection
        console.log('LECTURER LOGIN RESULT:', data);
        app.me = data.lecturer || data;
        app.userType = 'lecturer';
        app.page = 'homepage';
        app.selectedBuilding = null;
        if (socket) {
            socket.userName = app.me.name;
        }
        updateUserDisplay();
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

    // Lecture start result: store building lecture and navigate to in-lecture page
    socket.on('lecture:start:result', (data) => {
        console.log('LECTURE START RESULT:', data);
        if (data.error) {
            // Show error in modal (homepage) or form (setup page)
            if (app.page === 'homepage') {
                app.quickLectureError = data.error;
                app.showStartLectureModal = true;
            } else {
                app.lectureError = data.error;
            }
        } else {
            // Store lecture in building and join lecture room
            if (app.selectedBuilding) {
                app.buildingLectures[app.selectedBuilding] = {
                    title: app.currentLectureTitle,
                    module: app.selectedModule,
                    lecturer: app.me.name
                };
            }

            app.currentLectureModule = app.selectedModule || '';
            app.studentCount = 0;

            app.page = 'inLecture';
            app.boardContent = '';
            app.chatMessages = [];
            if (socket) {
                socket.emit('lecture:join', { lectureTitle: app.currentLectureTitle, userType: app.userType });
            }
            // Initialise board for lecturer
            app.$nextTick(() => {
                if (app.isLecturer && app.$refs.lecturerBoard && app.boardContent) {
                    app.$refs.lecturerBoard.innerHTML = app.boardContent;
                }
            });
        }
    });

    socket.on('lecture:start:error', (msg) => {
        app.lectureError = msg;
    });

    // Building lecture updates: receive broadcast when lectures start/end in buildings
    socket.on('lecture:building:update', (data) => {
        if (data.building && data.lecture) {
            app.buildingLectures[Number(data.building)] = data.lecture;
        }
    });

    // Board updates
    socket.on('board:update', (data) => {
        if (data.lectureTitle === app.currentLectureTitle) {
            // For lecturer: update the ref directly without using v-html
            if (app.isLecturer) {
                // Lecturer: update the contenteditable div directly via ref
                // Only update if content is different to avoid cursor reset
                const boardElement = app.$refs.lecturerBoard;
                if (boardElement && data.content !== boardElement.innerHTML) {
                    // Save cursor position before update
                    const selection = window.getSelection();
                    let cursorPos = 0;
                    let textNode = null;
                    
                    if (selection.rangeCount > 0 && boardElement.contains(selection.anchorNode)) {
                        const range = selection.getRangeAt(0);
                        textNode = range.startContainer;
                        cursorPos = range.startOffset;
                    }
                    
                    // Update content directly (bypass Vue's v-html)
                    boardElement.innerHTML = data.content;
                    app.boardContent = data.content;
                    
                    // Restore cursor position
                    if (textNode && boardElement.firstChild) {
                        try {
                            const newRange = document.createRange();
                            const newSelection = window.getSelection();
                            const node = boardElement.firstChild;
                            const maxPos = node.textContent ? node.textContent.length : 0;
                            const pos = Math.min(cursorPos, maxPos);
                            newRange.setStart(node, pos);
                            newRange.setEnd(node, pos);
                            newSelection.removeAllRanges();
                            newSelection.addRange(newRange);
                        } catch (e) {
                            //  Ignore
                        }
                    }
                }
            } else {
                // Students only need to update the content
                app.boardContent = data.content;
            }
        }
    });

    // Chat messages
    socket.on('chat:message', (data) => {
        if (data.lectureTitle === app.currentLectureTitle) {
            app.chatMessages.push({
                user: data.user,
                message: data.message,
                time: data.time || new Date().toLocaleTimeString()
            });
            // Auto-scroll to bottom
            setTimeout(() => {
                const chatContainer = document.getElementById('chat-messages');
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
            }, 100);
        }
    });

    // Module update
    socket.on('modules:update:result', (data) => {
        if (data.error) {
            app.settingsError = data.error;
        } else {
            app.settingsSuccess = 'Modules updated successfully!';
            // Update user's modules
            if (app.me) {
                app.me.modules = data.modules;
            }
            setTimeout(() => {
                app.settingsSuccess = '';
            }, 3000);
        }
    });

    socket.on('lecture:count:update', (data) => {
    if (data.lectureTitle === app.currentLectureTitle) {
        app.studentCount = data.studentCount;
        }
    });


    socket.on('modules:update:error', (msg) => {
        app.settingsError = msg;
    });

    socket.on('disconnect', function () {
        console.log('Socket disconnected');
        app.connected = false;
        updateUserDisplay();

        socket = null;
    });
}

