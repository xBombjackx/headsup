const chatContainer = document.getElementById('chat-container');
const socket = new WebSocket('ws://localhost:8765'); 
socket.onmessage = function (event) {
    const data = JSON.parse(event.data);

    const messageElement = document.createElement('div');
    messageElement.className = 'chat-message ' + data.platform.toLowerCase();

    const authorElement = document.createElement('span');
    authorElement.className = 'author';
    authorElement.textContent = data.author + ':';
       authorElement.style.color = data.color;

    const contentElement = document.createElement('span');
    contentElement.className = 'message-content';
    contentElement.textContent = data.message;

    messageElement.appendChild(authorElement);
    messageElement.appendChild(contentElement);
    chatContainer.appendChild(messageElement);
    
    window.scrollTo(0, document.body.scrollHeight);
};