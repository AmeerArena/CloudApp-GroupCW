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

        // homepage/building selection
        selectedBuilding: null,
        buildingLectures: {}, // Map of building number to lecture data
        showStartLectureModal: false,
        quickLectureTitle: '',
        quickSelectedModule: '',
        quickLectureError: '',

        // lecture setup
        lectureTitle: '',
        selectedModule: '',
        lectureError: '',

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
            this.selectedBuilding = buildingNumber;
            // Close modal if open
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

            // Store lecture title for in-lecture page
            this.currentLectureTitle = this.quickLectureTitle;
            this.selectedModule = this.quickSelectedModule;

            // Emit event to start lecture with building info
            socket.emit('lecture:start', {
                title: this.quickLectureTitle,
                module: this.quickSelectedModule,
                lecturer: this.me.name,
                building: this.selectedBuilding
            });

            // Close modal
            this.showStartLectureModal = false;
            // Clear form
            this.quickLectureTitle = '';
            this.quickSelectedModule = '';
        },

        hasLectureInBuilding(buildingNumber) {
            // Check if there's an active lecture in this building
            return this.buildingLectures[buildingNumber] !== undefined;
        },

        attendLecture() {
            if (!this.selectedBuilding || !this.hasLectureInBuilding(this.selectedBuilding)) {
                return;
            }
            // Get lecture data for this building
            const lecture = this.buildingLectures[this.selectedBuilding];
            this.currentLectureTitle = lecture.title || `Lecture in Building ${this.selectedBuilding}`;
            this.page = 'inLecture';
            // Join lecture room
            if (socket) {
                socket.emit('lecture:join', { lectureTitle: this.currentLectureTitle });
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

            // Store lecture title for in-lecture page
            this.currentLectureTitle = this.lectureTitle;

            // Emit event to start lecture with building info
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
        app.userType = 'student'; // Mark as student
        // Navigate to homepage to select building
        app.page = 'homepage';
        app.selectedBuilding = null;
        // Store user name for chat
        if (socket) {
            socket.userName = app.me.name;
        }
    });

    // Login lecturer
    socket.on('lecturer:login:error', (msg) => {
        app.loginError = msg;
    });

    socket.on('lecturer:login:result', (data) => {
        console.log('LECTURER LOGIN RESULT:', data);
        app.me = data.lecturer || data;
        app.userType = 'lecturer'; // Mark as lecturer
        // Navigate to homepage to select building
        app.page = 'homepage';
        app.selectedBuilding = null;
        // Store user name for chat
        if (socket) {
            socket.userName = app.me.name;
        }
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

    // Lecture start
    socket.on('lecture:start:result', (data) => {
        console.log('LECTURE START RESULT:', data);
        if (data.error) {
            // Show error in appropriate place
            if (app.page === 'homepage') {
                app.quickLectureError = data.error;
                app.showStartLectureModal = true; // Reopen modal to show error
            } else {
                app.lectureError = data.error;
            }
        } else {
            // Store lecture in building
            if (app.selectedBuilding) {
                app.buildingLectures[app.selectedBuilding] = {
                    title: app.currentLectureTitle,
                    module: app.selectedModule,
                    lecturer: app.me.name
                };
            }
            // Navigate to in-lecture page
            app.page = 'inLecture';
            app.boardContent = '';
            app.chatMessages = [];
            // Join lecture room
            if (socket) {
                socket.emit('lecture:join', { lectureTitle: app.currentLectureTitle });
            }
            // Initialize board content for lecturer after Vue renders
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

    // Building lecture updates (when lectures start/end)
    socket.on('lecture:building:update', (data) => {
        if (data.building && data.lecture) {
            app.buildingLectures[data.building] = data.lecture;
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

    socket.on('modules:update:error', (msg) => {
        app.settingsError = msg;
    });

    socket.on('disconnect', function () {
        console.log('Socket disconnected');
        app.connected = false;
        socket = null;
    });
}

