// Simulation related variables
let canvas = document.getElementById('simulationCanvas');
let ctx = canvas.getContext('2d');
let simulationActive = false;
let fieldGrid = [];
let gridSize = 10; // 10x10 grid
let cellSize = canvas.width / gridSize;
let hotspots = [];
let dronePosition = { x: Math.floor(gridSize / 2), y: Math.floor(gridSize / 2) };
let sprayAnimation = false;
let sprayRadius = 0;
let sprayFrames = 0;
let spraying = false;
let pesticide = '';

// DOM elements for control buttons
const moveUpBtn = document.getElementById('moveUp');
const moveDownBtn = document.getElementById('moveDown');
const moveLeftBtn = document.getElementById('moveLeft');
const moveRightBtn = document.getElementById('moveRight');
const sprayBtn = document.getElementById('spray');

// Event listeners for drone controls
document.addEventListener('DOMContentLoaded', function() {
    moveUpBtn.addEventListener('click', () => moveDrone(0, -1));
    moveDownBtn.addEventListener('click', () => moveDrone(0, 1));
    moveLeftBtn.addEventListener('click', () => moveDrone(-1, 0));
    moveRightBtn.addEventListener('click', () => moveDrone(1, 0));
    sprayBtn.addEventListener('click', sprayPesticide);
    
    // Keyboard controls
    document.addEventListener('keydown', handleKeyboardControls);
    
    // Initialize canvas
    drawField();
});

// Initialize field with data from disease detection
function initializeField(data) {
    if (!data) return;
    
    fieldGrid = data.grid;
    hotspots = data.hotspots;
    
    // Check if this is a maturity analysis view
    isMaturityAnalysis = data.is_maturity_analysis || false;
    
    // Reset drone to center
    dronePosition = { x: Math.floor(gridSize / 2), y: Math.floor(gridSize / 2) };
    
    // Draw the initial field
    drawField();
}

// Start simulation
function startSimulation() {
    simulationActive = true;
    animate();
}

// Stop simulation
function stopSimulation() {
    simulationActive = false;
}

// Animation loop
function animate() {
    if (!simulationActive) return;
    
    drawField();
    
    // If spraying animation is active, continue animation
    if (sprayAnimation) {
        animateSpray();
    }
    
    requestAnimationFrame(animate);
}

// Draw the field
function drawField() {
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw grid
    for (let y = 0; y < gridSize; y++) {
        for (let x = 0; x < gridSize; x++) {
            // Alternating green checkerboard pattern
            if ((x + y) % 2 === 0) {
                ctx.fillStyle = '#4CAF50'; // Darker green
            } else {
                ctx.fillStyle = '#8BC34A'; // Lighter green
            }
            
            ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
            
            // Draw grid lines
            ctx.strokeStyle = '#2E7D32';
            ctx.strokeRect(x * cellSize, y * cellSize, cellSize, cellSize);
        }
    }
    
    // Draw hotspots - either disease areas or coconut trees based on analysis type
    hotspots.forEach(hotspot => {
        const centerX = hotspot.x * cellSize + cellSize / 2;
        const centerY = hotspot.y * cellSize + cellSize / 2;
        
        if (isMaturityAnalysis) {
            // Draw coconut tree with maturity indicator
            drawCoconutTree(centerX, centerY, hotspot.maturity);
        } else {
            // Yellow circle indicating disease (original behavior)
            ctx.beginPath();
            ctx.arc(
                centerX,
                centerY,
                cellSize / 3,
                0,
                Math.PI * 2
            );
            ctx.fillStyle = 'rgba(255, 255, 0, 0.7)';
            ctx.fill();
            ctx.strokeStyle = '#FFA000';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    });
    
    // Draw drone
    drawDrone(dronePosition.x, dronePosition.y);
}

// Draw the drone
function drawDrone(x, y) {
    const centerX = x * cellSize + cellSize / 2;
    const centerY = y * cellSize + cellSize / 2;
    const droneSize = cellSize * 0.7;
    
    // Drone body (circle)
    ctx.beginPath();
    ctx.arc(centerX, centerY, droneSize / 3, 0, Math.PI * 2);
    ctx.fillStyle = '#303F9F';
    ctx.fill();
    ctx.strokeStyle = '#1A237E';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Drone arms
    const armLength = droneSize / 2;
    
    // Draw arms in four directions
    for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 2) {
        const armEndX = centerX + Math.cos(angle) * armLength;
        const armEndY = centerY + Math.sin(angle) * armLength;
        
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(armEndX, armEndY);
        ctx.strokeStyle = '#90A4AE';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // Drone propellers
        ctx.beginPath();
        ctx.arc(armEndX, armEndY, droneSize / 8, 0, Math.PI * 2);
        ctx.fillStyle = '#CFD8DC';
        ctx.fill();
        ctx.strokeStyle = '#607D8B';
        ctx.lineWidth = 1;
        ctx.stroke();
    }
}

// Move the drone
function moveDrone(dx, dy) {
    if (!simulationActive) return;
    
    const newX = dronePosition.x + dx;
    const newY = dronePosition.y + dy;
    
    // Check boundaries
    if (newX >= 0 && newX < gridSize && newY >= 0 && newY < gridSize) {
        dronePosition.x = newX;
        dronePosition.y = newY;
        
        // Update user progress tracking for hints
        if (typeof userProgress !== 'undefined') {
            userProgress.movedDrone = true;
        }
    }
}

// Spray pesticide
function sprayPesticide() {
    if (!simulationActive) return;
    
    // Get selected pesticide
    pesticide = document.getElementById('pesticideSelect').value;
    
    if (!pesticide) {
        showAlert('Please select a pesticide first', 'warning');
        return;
    }
    
    // Start spray animation
    sprayAnimation = true;
    sprayRadius = 0;
    sprayFrames = 0;
    spraying = true;
    
    // Check if drone is over a hotspot
    const hotspot = hotspots.find(h => h.x === dronePosition.x && h.y === dronePosition.y);
    if (hotspot) {
        if (isMaturityAnalysis) {
            // For coconut trees, don't "treat" them but inform about maturity
            let message = '';
            
            if (hotspot.maturity === 'immature') {
                message = 'This coconut tree is still immature. No action needed at this time.';
            } else if (hotspot.maturity === 'mature') {
                message = 'This coconut tree is mature but not yet ready for harvest. Continue monitoring.';
            } else if (hotspot.maturity === 'ready_for_harvest') {
                message = 'This coconut tree is ready for harvest! Coconuts can be collected now.';
            } else {
                message = 'Coconut tree examined. Assessment complete.';
            }
            
            showAlert(message, 'info');
        } else {
            // For disease hotspots, remove them (treat the disease)
            hotspots = hotspots.filter(h => h.x !== dronePosition.x || h.y !== dronePosition.y);
            showAlert(`Successfully sprayed ${formatPesticideName(pesticide)} on diseased area!`, 'success');
            
            // Update user progress for hints
            if (typeof userProgress !== 'undefined') {
                userProgress.sprayedPesticide = true;
            }
            
            // Show congratulations if all hotspots are treated
            if (hotspots.length === 0) {
                setTimeout(() => {
                    showAlert('Great job! You\'ve successfully treated all diseased areas in this field.', 'success');
                }, 1000);
            }
        }
    } else {
        // Inform user they're not over a hotspot
        if (isMaturityAnalysis) {
            showAlert('No coconut tree at this location. Move to a tree to examine it.', 'info');
        } else {
            showAlert('No disease detected at this location. Move to a yellow spot to spray effectively.', 'info');
        }
    }
}

// Animate spray effect
function animateSpray() {
    if (!sprayAnimation) return;
    
    const centerX = dronePosition.x * cellSize + cellSize / 2;
    const centerY = dronePosition.y * cellSize + cellSize / 2;
    
    // Draw spray circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, sprayRadius, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 200, 200, 0.3)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(0, 150, 150, 0.5)';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Increase radius
    sprayRadius += 2;
    sprayFrames++;
    
    // End animation after certain frames
    if (sprayFrames > 20) {
        sprayAnimation = false;
        spraying = false;
    }
}

// Handle keyboard controls
function handleKeyboardControls(e) {
    if (!simulationActive) return;
    
    switch (e.key) {
        case 'ArrowUp':
            moveDrone(0, -1);
            e.preventDefault();
            break;
        case 'ArrowDown':
            moveDrone(0, 1);
            e.preventDefault();
            break;
        case 'ArrowLeft':
            moveDrone(-1, 0);
            e.preventDefault();
            break;
        case 'ArrowRight':
            moveDrone(1, 0);
            e.preventDefault();
            break;
        case ' ': // Space bar
            sprayPesticide();
            e.preventDefault();
            break;
    }
}

// Format pesticide name for display
function formatPesticideName(code) {
    if (!code) return 'Unknown Pesticide';
    
    // Convert snake_case to Title Case
    return code
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Draw a coconut tree with maturity indicator
function drawCoconutTree(x, y, maturityLevel) {
    // Set colors based on maturity level
    let trunkColor = '#8B4513'; // Brown
    let leafColor = '#2E7D32';  // Dark green
    let coconutColor = '#F5F5DC'; // Light beige
    
    // Adjust colors based on maturity
    if (maturityLevel === 'immature') {
        leafColor = '#4CAF50'; // Lighter green for young trees
        coconutColor = '#A5D6A7'; // Light green coconuts
    } else if (maturityLevel === 'mature') {
        leafColor = '#2E7D32'; // Darker green
        coconutColor = '#CDDC39'; // Yellowish green
    } else if (maturityLevel === 'ready_for_harvest') {
        leafColor = '#1B5E20'; // Even darker green
        coconutColor = '#8B4513'; // Brown coconuts ready for harvest
    }
    
    // Draw trunk
    ctx.beginPath();
    ctx.moveTo(x, y + cellSize * 0.3);
    ctx.lineTo(x - cellSize * 0.1, y);
    ctx.lineTo(x + cellSize * 0.1, y);
    ctx.closePath();
    ctx.fillStyle = trunkColor;
    ctx.fill();
    ctx.strokeStyle = '#5D4037';
    ctx.lineWidth = 1;
    ctx.stroke();
    
    // Draw palm leaves (fronds)
    const numLeaves = 6;
    const leafLength = cellSize * 0.4;
    
    for (let i = 0; i < numLeaves; i++) {
        const angle = (i * Math.PI * 2) / numLeaves;
        const leafEndX = x + Math.cos(angle) * leafLength;
        const leafEndY = y + Math.sin(angle) * leafLength;
        
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(leafEndX, leafEndY);
        ctx.strokeStyle = leafColor;
        ctx.lineWidth = 3;
        ctx.stroke();
        
        // Draw leaf tip
        ctx.beginPath();
        ctx.arc(leafEndX, leafEndY, cellSize * 0.05, 0, Math.PI * 2);
        ctx.fillStyle = leafColor;
        ctx.fill();
    }
    
    // Draw coconuts (only on mature trees)
    if (maturityLevel === 'mature' || maturityLevel === 'ready_for_harvest') {
        const numCoconuts = 3;
        const coconutRadius = cellSize * 0.08;
        const coconutDistance = cellSize * 0.2;
        
        for (let i = 0; i < numCoconuts; i++) {
            const coconutAngle = (i * Math.PI * 2) / numCoconuts;
            const coconutX = x + Math.cos(coconutAngle) * coconutDistance;
            const coconutY = y + Math.sin(coconutAngle) * coconutDistance;
            
            ctx.beginPath();
            ctx.arc(coconutX, coconutY, coconutRadius, 0, Math.PI * 2);
            ctx.fillStyle = coconutColor;
            ctx.fill();
            ctx.strokeStyle = '#5D4037';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }
    
    // Add a highlight indicator for the maturity level
    let indicatorColor = '#2196F3'; // Blue for immature
    if (maturityLevel === 'mature') {
        indicatorColor = '#FF9800'; // Orange for mature
    } else if (maturityLevel === 'ready_for_harvest') {
        indicatorColor = '#4CAF50'; // Green for ready to harvest
    }
    
    // Draw indicator at the base of the tree
    ctx.beginPath();
    ctx.arc(x, y + cellSize * 0.3, cellSize * 0.1, 0, Math.PI * 2);
    ctx.fillStyle = indicatorColor;
    ctx.fill();
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 1;
    ctx.stroke();
}
