const express = require('express');
const http = require('http');
const { WebSocketServer } = require('ws');
const path = require('path');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: '/ws' });

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
    res.render('game');
});

const questions = [
    { question: "What is the capital of France?", options: ["Berlin", "Madrid", "Paris", "Rome"], answer: "C" },
    { question: "Which planet is known as the Red Planet?", options: ["Earth", "Mars", "Jupiter", "Venus"], answer: "B" },
    { question: "What is the largest ocean on Earth?", options: ["Atlantic", "Indian", "Arctic", "Pacific"], answer: "D" },
    { question: "Who wrote 'Romeo and Juliet'?", options: ["Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain"], answer: "B" },
    { question: "What is the chemical symbol for water?", options: ["O2", "CO2", "H2O", "NaCl"], answer: "C" },
    { question: "How many continents are there?", options: ["5", "6", "7", "8"], answer: "C" }
];
let currentQuestion = null;
let diceValue = 0;

wss.on('connection', (ws) => {
    console.log('A client connected.');

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            console.log('SERVER: Received message:', data);

            if (data.action === 'requestDiceRoll') {
                diceValue = Math.floor(Math.random() * 6) + 1;
                currentQuestion = questions[Math.floor(Math.random() * questions.length)];
                
                broadcast({ 
                    action: 'showQuiz',
                    sub_action: 'waitForAnswer',
                    diceValue: diceValue, 
                    question: currentQuestion.question,
                    options: currentQuestion.options
                });
            } 
            else if (data.action === 'submitAnswer') {
                const isCorrect = data.answer === currentQuestion.answer;
                
                broadcast({ 
                    action: 'answerResult',
                    sub_action: 'waitForFist',
                    correct: isCorrect, 
                    correctAnswer: currentQuestion.answer,
                    diceValue: isCorrect ? diceValue : 0 
                });
            }
        } catch (error) {
            console.error("SERVER: Error processing message:", error);
        }
    });

    ws.on('close', () => {
        console.log('A client disconnected.');
    });
});

function broadcast(data) {
    // --- DEBUGGING STEP ---
    // This log is crucial. It confirms the server is sending the response.
    console.log('SERVER: Broadcasting message to all clients:', data);
    const messageString = JSON.stringify(data);
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(messageString);
        }
    });
}

const PORT = 3000;
server.listen(PORT, () => {
    console.log(`Game server running on http://localhost:${PORT}`);
    console.log(`WebSocket server is running on ws://localhost:${PORT}/ws`);
});

