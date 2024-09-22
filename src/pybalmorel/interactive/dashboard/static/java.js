// Initial values
let output_type = ['countries', 'regions', 'areas'];
let consoleOutput = document.getElementById('consoleOutput');
let codeSnippet = document.getElementById('codeSnippet');
window.to_be_connected = [];
window.connections = {};
updateDisplay();

// Store the working directory in save to path
get_wkdir()

// Resize the window and center
resizeAndCenterWindow();

function updateDisplay() {
    // Clear
    document.querySelectorAll('.connection-line').forEach(line => line.remove());
    window.connected_lines = {
        'countries' : {},
        'regions' : {},
        'areas' : {}
    }
    for (let i = 1; i <= 3; i++) {
        // Get input value
        let input = document.getElementById(`input${i}`).value;
        
        // Split by commas
        let text = input.split(',')
        
        // Get the output section
        let outputSection = document.getElementById(output_type[i-1]);
        outputSection.innerHTML = ''; // Clear existing content
        
        // Iterate over text pieces and create divs for each one
        text.forEach(element => {
            if (element.trim()) {  // Ensure there's text after trimming whitespace
                const div = document.createElement('div');
                div.className = 'output-item';
                div.id = element.trim().replace(/\s+/g, '_');
                div.style.position = 'relative';
                div.style.zIndex = 10;
                div.textContent = element.trim().replace(/\s+/g, '_');
                outputSection.appendChild(div);
                div.style.backgroundColor = 'rgb(185, 185, 185)';
                
                // Add function
                div.addEventListener('click', click)
                
                // Store
                window.connected_lines[output_type[i-1]][div.id] = [];
            }
        });
        
        // Create connections    
        for (let node1 in window.connected_lines[output_type[i-1]]) {
            if (window.connections.hasOwnProperty(node1)) {
                let node1_array = window.connections[node1];
                node1_array.forEach(node2 => {
                    console.log(`Connection from ${node1} to ${node2}`);
                    window.connected_lines[output_type[i-1]][node1].push(node2);
                    drawConnection(node1, node2);
                })
            }
        }
    }
    codeSnippet.innerHTML = JSON.stringify(window.connected_lines, null, 2);
}

// Add event listeners to inputs to trigger updateDisplay on every keystroke
for (let i = 1; i <= 3; i++) {
    document.getElementById(`input${i}`).addEventListener('input', updateDisplay);
}

function click() {
    if (window.to_be_connected.length === 0) {
        // If nothing selected, make this node active
        this.style.backgroundColor = 'rgb(153, 238, 154)';
        window.to_be_connected = [this.id, this.parentNode.id];
    } else if (window.to_be_connected[0] === this.id) {
        // If this node is selected, make it inactive 
        this.style.backgroundColor = 'rgb(185, 185, 185)';
        window.to_be_connected = [];
    } else {
        // Check if connection is valid
        let firstId = document.getElementById(window.to_be_connected[0]);
        let firstType = window.to_be_connected[1];
        let thisType = this.parentNode.id;
        if (firstType === thisType) {
            firstId.style.backgroundColor = 'rgb(185, 185, 185)';
            consoleOutput.innerHTML = `<br>Can't make connections between ${firstType} and ${thisType}<br>`;
            consoleOutput.style.color = 'red';
            window.to_be_connected = [];
        } else if ((firstType === 'countries' && thisType === 'areas') || (firstType === 'areas' && thisType === 'countries')) {
            firstId.style.backgroundColor = 'rgb(185, 185, 185)';
            consoleOutput.innerHTML = `<br>Can't make connections between countries and areas<br>`;
            consoleOutput.style.color = 'red';
            window.to_be_connected = [];
        } else {
            firstId.style.backgroundColor = 'rgb(185, 185, 185)';
            consoleOutput.innerHTML = `<br>Connection made!<br>`;
            consoleOutput.style.color = 'green';
            
            // Make correct direction
            if ((firstType === 'countries' && thisType == 'regions') || (firstType === 'regions' && thisType == 'areas')) {
                initiate_or_append(window.connections, firstId.id, this.id)
                // console.log(window.connections);
            } else {
                initiate_or_append(window.connections, this.id, firstId.id)
                // console.log(window.connections);
            }

            window.to_be_connected = [];
            updateDisplay();
        }
    }
}

function drawConnection(firstId, secondId) {
    // Get divs
    const firstDiv = document.getElementById(firstId);
    const secondDiv = document.getElementById(secondId);

    // Insert a line between the two divs
    const line = document.createElement('div');
    line.className = 'connection-line';
    document.body.appendChild(line);
    
    const updateLinePosition = () => {
        const firstRect = firstDiv.getBoundingClientRect();
        const secondRect = secondDiv.getBoundingClientRect();
        const x1 = firstRect.left + firstRect.width / 2 ;
        const y1 = firstRect.top + firstRect.height / 2 + window.scrollY;
        const x2 = secondRect.left + secondRect.width / 2;
        const y2 = secondRect.top + secondRect.height / 2 + window.scrollY;

        line.style.zIndex = 1;
        line.style.position = 'absolute';
        line.style.width = `${Math.hypot(x2 - x1, y2 - y1)}px`;
        line.style.height = '2px';
        line.style.backgroundColor = 'black';
        line.style.transformOrigin = '0 0';
        line.style.transform = `rotate(${Math.atan2(y2 - y1, x2 - x1)}rad)`;
        line.style.left = `${x1}px`;
        line.style.top = `${y1}px`;
    };

    updateLinePosition();
}

function move_lines(x, y) {
    document.querySelectorAll('.connection-line').forEach(line => {
        line.style.transform = `translate(${x}px, ${y}px)`;
    });
}

window.addEventListener('scroll', updateLinePosition(window.scrollX, window.scrollY));

function initiate_or_append(dictionary, key, entry) {
    if (dictionary.hasOwnProperty(key)) {
        dictionary[key].push(entry);
    } else {
        dictionary[key] = [entry];
    }
}


function resizeAndCenterWindow() {
    const screenWidth = window.screen.availWidth;
    const screenHeight = window.screen.availHeight;
    const newWidth = screenWidth * 0.5;
    const newHeight = screenHeight * 0.6;
    const newX = (screenWidth - newWidth) / 2;
    const newY = (screenHeight - newHeight) / 2;

    window.resizeTo(newWidth, newHeight);
    window.moveTo(newX, newY);
}


// Python functions
async function create_incfiles() {
    let output = codeSnippet.innerHTML;

    let path_input = document.getElementById('save_to_path');
    let save_path = path_input.value;
    
    // Call Python
    await eel.create_incfiles(output, save_path)();

    // Output console
    consoleOutput.innerHTML = `<br>.inc files succesfully generated to ${save_path}<br>`;
    consoleOutput.style.color = 'green';
}


async function get_wkdir() {
    // Get working directory from python
    let wkdir = await eel.get_wkdir()();
    
    let path_input = document.getElementById('save_to_path');
    path_input.value = wkdir;
    
}

