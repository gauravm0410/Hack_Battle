document.addEventListener('DOMContentLoaded', () => {
    const board = document.getElementById('game-board');
    const diceResultEl = document.getElementById('dice-result');
    const gameStatusEl = document.getElementById('game-status');
    const quizSection = document.getElementById('quiz-section');
    const quizQuestionEl = document.getElementById('quiz-question');
    const quizOptionsContainer = document.getElementById('quiz-options');
    const pawn = document.getElementById('pawn');
    const pawnPosEl = document.getElementById('pawn-pos');

    let currentPosition = 1;
    const snakesAndLadders = {
        3: 24, 12: 41, 28: 52, 51: 88, 62: 95, // Ladders
        48: 18, 67: 33, 89: 50, 98: 7,       // Snakes
    };

    const WEBSOCKET_URL = `ws://${window.location.host}/ws`;
    const ws = new WebSocket(WEBSOCKET_URL);

    ws.onopen = () => console.log('Connected to game server.');
    ws.onclose = () => console.log('Disconnected from game server.');
    ws.onerror = (err) => console.error('WebSocket error:', err);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Received from server:', data);

        if (data.action === 'showQuiz') {
            diceResultEl.textContent = data.diceValue;
            gameStatusEl.textContent = `You rolled a ${data.diceValue}! Answer the question.`;
            quizQuestionEl.textContent = data.question;
            const options = quizOptionsContainer.children;
            for (let i = 0; i < options.length; i++) {
                options[i].textContent = `${['A', 'B', 'C', 'D'][i]}) ${data.options[i]}`;
                options[i].classList.remove('bg-green-500', 'bg-red-500');
                options[i].classList.add('bg-gray-700');
            }
            quizSection.classList.remove('hidden');
        } 
        else if (data.action === 'answerResult') {
            const options = quizOptionsContainer.children;
            const answerIndex = ['A', 'B', 'C', 'D'].indexOf(data.correctAnswer);
            
            // Highlight the correct answer
            if (answerIndex !== -1) {
                 options[answerIndex].classList.remove('bg-gray-700');
                 options[answerIndex].classList.add('bg-green-500');
            }

            if (data.correct) {
                gameStatusEl.textContent = `Correct! Moving ${data.diceValue} steps.`;
                movePlayer(data.diceValue);
            } else {
                gameStatusEl.textContent = `Wrong! The correct answer was ${data.correctAnswer}. Try again next turn.`;
            }

            setTimeout(() => {
                quizSection.classList.add('hidden');
                diceResultEl.textContent = '...';
                gameStatusEl.textContent = 'Close your fist for the next roll.';
            }, 3000);
        }
    };
    
    function movePlayer(steps) {
        let newPos = currentPosition + steps;
        if (newPos > 100) newPos = 100;
        
        updatePawnPosition(newPos);
        currentPosition = newPos;

        // Check for snake or ladder after a delay
        setTimeout(() => {
            let finalPos = snakesAndLadders[currentPosition] || currentPosition;
            if (finalPos !== currentPosition) {
                 updatePawnPosition(finalPos);
                 currentPosition = finalPos;
            }
            if (currentPosition === 100) {
                gameStatusEl.textContent = "Congratulations! You won!";
            }
        }, 600);
    }

    function createBoard() {
        // This generates the board from 100 down to 1
        for (let i = 0; i < 10; i++) {
            for (let j = 0; j < 10; j++) {
                const cell = document.createElement('div');
                cell.className = 'board-cell border border-gray-600';
                
                const row = i;
                const col = j;
                let cellNumber;

                if (row % 2 === 0) { // Even rows (0, 2, 4...)
                    cellNumber = 100 - (row * 10) - col;
                } else { // Odd rows
                    cellNumber = 100 - (row * 10) - (9 - col);
                }

                if ((row + col) % 2 === 0) {
                     cell.classList.add('bg-gray-700');
                } else {
                     cell.classList.add('bg-gray-800');
                }

                const numberSpan = document.createElement('span');
                numberSpan.textContent = cellNumber;
                cell.appendChild(numberSpan);
                board.appendChild(cell);
            }
        }
    }
    
    function updatePawnPosition(position) {
        currentPosition = position;
        pawnPosEl.textContent = position;
        const { row, col } = getCoordinatesFromPosition(position);
        pawn.style.left = `calc(${col * 10 + 1}%)`;
        pawn.style.bottom = `calc(${row * 10 + 1}%)`;
    }

    function getCoordinatesFromPosition(position) {
        const pos = position - 1;
        const row = Math.floor(pos / 10);
        let col = pos % 10;
        if (row % 2 !== 0) { // On odd rows (from bottom, 0-indexed), reverse column
            col = 9 - col;
        }
        return { row, col };
    }

    // Initial setup
    createBoard();
    updatePawnPosition(1);
});

