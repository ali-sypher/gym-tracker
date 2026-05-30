/* -------------------------------------------------------------
   ANTIGRAVITY GYM - INTERACTIVE FRONTEND APPLICATION CLIENT
------------------------------------------------------------- */

let progressChart = null;

document.addEventListener('DOMContentLoaded', function() {
    // 1. Initialize Auto-dismissal for Flashed Messages (Toast Alerts)
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100px)';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 5000);
    });

    // 2. Mobile Navigation Toggle Menu
    const navToggle = document.querySelector('.mobile-nav-toggle');
    const navbar = document.querySelector('.navbar');
    if (navToggle && navbar) {
        navToggle.addEventListener('click', function() {
            navbar.classList.toggle('active');
            const icon = navToggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-bars');
                icon.classList.toggle('fa-xmark');
            }
        });
    }
});

// -------------------------------------------------------------
// MEMBER DASHBOARD - DYNAMIC CHART.JS INITIALIZATION
// -------------------------------------------------------------
function initializeProgressChart() {
    const ctx = document.getElementById('workoutProgressChart');
    if (!ctx) return; // Only execute if canvas exists (member dashboard)

    fetch('/api/workouts/history')
        .then(response => response.json())
        .then(data => {
            const noDataOverlay = document.getElementById('noChartDataMessage');
            
            if (!data || data.length === 0) {
                if (noDataOverlay) noDataOverlay.style.display = 'flex';
                ctx.style.display = 'none';
                return;
            } else {
                if (noDataOverlay) noDataOverlay.style.display = 'none';
                ctx.style.display = 'block';
            }

            // Organize data: group workouts chronologically by date
            // We want to track the maximum weight for each main exercise over time
            const uniqueDates = [...new Set(data.map(w => w.date))].sort();
            
            // Count unique exercise names and grab top 3 by frequency
            const exerciseCounts = {};
            data.forEach(w => {
                exerciseCounts[w.exercise_name] = (exerciseCounts[w.exercise_name] || 0) + 1;
            });
            
            const topExercises = Object.keys(exerciseCounts)
                .sort((a, b) => exerciseCounts[b] - exerciseCounts[a])
                .slice(0, 3); // Track top 3 exercises

            // Design color schemes for top exercises
            const colorPalettes = [
                { stroke: '#00f2fe', fill: 'rgba(0, 242, 254, 0.05)' }, // Cyber Cyan
                { stroke: '#00e676', fill: 'rgba(0, 230, 118, 0.05)' }, // Emerald Green
                { stroke: '#ffb300', fill: 'rgba(255, 179, 0, 0.05)' }  // Golden Orange
            ];

            // Build datasets
            const datasets = topExercises.map((exercise, index) => {
                const palette = colorPalettes[index % colorPalettes.length];
                
                // For each date, find the maximum weight logged for this exercise
                const chartData = uniqueDates.map(date => {
                    const logs = data.filter(w => w.date === date && w.exercise_name.toLowerCase() === exercise.toLowerCase());
                    if (logs.length === 0) return null; // Span gaps or ignore
                    return Math.max(...logs.map(w => w.weight_lbs));
                });

                return {
                    label: exercise,
                    data: chartData,
                    borderColor: palette.stroke,
                    backgroundColor: palette.fill,
                    borderWidth: 3,
                    pointBackgroundColor: palette.stroke,
                    pointBorderColor: '#121829',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    tension: 0.3,
                    spanGaps: true
                };
            });

            // Destroy existing chart to prevent canvas reuse errors on redraws
            if (progressChart) {
                progressChart.destroy();
            }

            progressChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: uniqueDates,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                color: '#94a3b8',
                                font: {
                                    family: 'Outfit',
                                    size: 12,
                                    weight: 'bold'
                                },
                                boxWidth: 15,
                                padding: 15
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1b233a',
                            titleColor: '#00f2fe',
                            bodyColor: '#f8fafc',
                            borderColor: 'rgba(255, 255, 255, 0.08)',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: true,
                            callbacks: {
                                label: function(context) {
                                    return ` ${context.dataset.label}: ${context.raw} lbs`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                color: 'rgba(255, 255, 255, 0.04)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: {
                                    family: 'Inter',
                                    size: 10
                                }
                            }
                        },
                        y: {
                            grid: {
                                color: 'rgba(255, 255, 255, 0.04)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#94a3b8',
                                font: {
                                    family: 'Inter',
                                    size: 10
                                },
                                callback: function(value) {
                                    return value + ' lbs';
                                }
                            }
                        }
                    }
                }
            });
        })
        .catch(err => console.error('Error drawing progress chart:', err));
}

// -------------------------------------------------------------
// WORKOUT LOGS CRUD - DYNAMIC AJAX INTERACTIONS
// -------------------------------------------------------------

// Open/Close Workout Edit Dialogs
function openEditModal(id, exercise, sets, reps, weight, date) {
    const modal = document.getElementById('editWorkoutModal');
    if (!modal) return;

    document.getElementById('edit_workout_id').value = id;
    document.getElementById('edit_exercise_name').value = exercise;
    document.getElementById('edit_sets').value = sets;
    document.getElementById('edit_reps').value = reps;
    document.getElementById('edit_weight_lbs').value = weight;
    document.getElementById('edit_workout_date').value = date;

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Stop background scrolling
}

function closeEditModal() {
    const modal = document.getElementById('editWorkoutModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Submit AJAX Edit Workout Put Request
function submitEditWorkout(event) {
    event.preventDefault();
    
    const id = document.getElementById('edit_workout_id').value;
    const data = {
        exercise_name: document.getElementById('edit_exercise_name').value,
        sets: parseInt(document.getElementById('edit_sets').value),
        reps: parseInt(document.getElementById('edit_reps').value),
        weight_lbs: parseFloat(document.getElementById('edit_weight_lbs').value),
        date: document.getElementById('edit_workout_date').value
    };

    fetch(`/api/workouts/${id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            closeEditModal();
            showDynamicToast('success', 'Workout details updated successfully!');
            
            // Instantly update standard table cell displays without fully reloading the page!
            const row = document.getElementById(`workout-row-${id}`);
            if (row) {
                row.cells[0].innerHTML = `<strong>${result.workout.date}</strong>`;
                row.cells[1].innerHTML = `<span class="exercise-badge">${result.workout.exercise_name}</span>`;
                row.cells[2].innerText = result.workout.sets;
                row.cells[3].innerText = result.workout.reps;
                row.cells[4].innerHTML = `${result.workout.weight_lbs} <span class="unit-text">lbs</span>`;
                
                // Volume Cell update
                const volume = result.workout.sets * result.workout.reps * result.workout.weight_lbs;
                row.cells[5].innerText = volume;

                // Re-bind click event to Edit trigger with updated details
                const editBtn = row.querySelector('.btn-edit');
                if (editBtn) {
                    editBtn.setAttribute('onclick', `openEditModal(${result.workout.id}, '${result.workout.exercise_name}', ${result.workout.sets}, ${result.workout.reps}, ${result.workout.weight_lbs}, '${result.workout.date}')`);
                }
            }
            
            // Re-render chart progress trends and recalculate dashboard totals
            initializeProgressChart();
            recalculateDashboardTotals();
        } else {
            showDynamicToast('danger', result.message || 'Error occurred updating workout.');
        }
    })
    .catch(err => {
        console.error('Error updating workout log:', err);
        showDynamicToast('danger', 'Could not establish connection to the server.');
    });
}

// Delete Workout Confirmation Flow
let workoutIdToDelete = null;

function confirmDeleteWorkout(id, exercise) {
    workoutIdToDelete = id;
    const nameLabel = document.getElementById('deleteWorkoutName');
    if (nameLabel) nameLabel.innerText = `"${exercise}"`;

    const modal = document.getElementById('deleteWorkoutModal');
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    const confirmBtn = document.getElementById('confirmDeleteBtn');
    if (confirmBtn) {
        confirmBtn.onclick = function() {
            executeDeleteWorkout(id);
        };
    }
}

function closeDeleteModal() {
    const modal = document.getElementById('deleteWorkoutModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
    workoutIdToDelete = null;
}

function executeDeleteWorkout(id) {
    fetch(`/api/workouts/${id}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        closeDeleteModal();
        if (result.success) {
            showDynamicToast('success', 'Workout log deleted successfully.');
            
            // Animate row removal and drop
            const row = document.getElementById(`workout-row-${id}`);
            if (row) {
                row.style.transform = 'translateX(-30px)';
                row.style.opacity = '0';
                setTimeout(() => {
                    row.remove();
                    
                    // Check if table is empty, if so, render empty placeholder
                    const tbody = document.querySelector('#workoutsTable tbody');
                    if (tbody && tbody.children.length === 0) {
                        tbody.innerHTML = `
                            <tr id="emptyTablePlaceholder">
                                <td colspan="7" class="empty-table-state">
                                    <i class="fa-solid fa-clipboard-question"></i>
                                    <p>No workout sessions logged yet. Get started by entering your first lift on the left!</p>
                                </td>
                            </tr>`;
                    }
                    
                    // Recalculate dashboard metrics and draw new chart
                    recalculateDashboardTotals();
                    initializeProgressChart();
                }, 300);
            }
        } else {
            showDynamicToast('danger', result.message || 'Could not delete workout.');
        }
    })
    .catch(err => {
        console.error('Delete request failed:', err);
        showDynamicToast('danger', 'Could not establish connection.');
    });
}

// -------------------------------------------------------------
// DYNAMIC STATISTICS RECALCULATION
// -------------------------------------------------------------
function recalculateDashboardTotals() {
    const table = document.getElementById('workoutsTable');
    if (!table) return;

    const rows = table.querySelectorAll('tbody tr:not(#emptyTablePlaceholder)');
    const totalSessions = rows.length;
    
    let totalSets = 0;
    let maxWeight = 0.0;

    rows.forEach(row => {
        const setsVal = parseInt(row.cells[2].innerText) || 0;
        const weightVal = parseFloat(row.cells[4].innerText) || 0.0;
        
        totalSets += setsVal;
        if (weightVal > maxWeight) {
            maxWeight = weightVal;
        }
    });

    // Update frontend metrics cards
    const statsWorkouts = document.getElementById('statsWorkouts');
    const statsSets = document.getElementById('statsSets');
    const statsWeight = document.getElementById('statsWeight');

    if (statsWorkouts) statsWorkouts.innerText = totalSessions;
    if (statsSets) statsSets.innerText = totalSets;
    if (statsWeight) statsWeight.innerHTML = `${maxWeight} <span class="unit">lbs</span>`;
}

// -------------------------------------------------------------
// ADMIN PANEL MODALS & ACTION BINDINGS
// -------------------------------------------------------------
function openManageMembershipModal(id, name, plan, status, price, endDate) {
    const modal = document.getElementById('manageMembershipModal');
    if (!modal) return;

    document.getElementById('modalMemberName').innerText = name;
    document.getElementById('modal_plan_name').value = plan;
    document.getElementById('modal_status').value = status;
    document.getElementById('modal_price').value = price;
    
    // Set standard renewal duration days based on plan type
    const durationInput = document.getElementById('modal_duration');
    if (plan === 'Weekly Trial') durationInput.value = '7';
    else if (plan === 'Monthly Pass') durationInput.value = '30';
    else if (plan === 'VIP Yearly') durationInput.value = '365';
    else durationInput.value = '30';

    // Set form action target dynamically
    const form = document.getElementById('manageMembershipForm');
    form.action = `/admin/membership/${id}/update`;

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeManageMembershipModal() {
    const modal = document.getElementById('manageMembershipModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Confirm Delete User dialog populator
function confirmDeleteUser(id, name, role) {
    const modal = document.getElementById('deleteUserModal');
    if (!modal) return;

    document.getElementById('deleteUserName').innerText = name;
    
    const roleLabel = document.getElementById('deleteUserRole');
    if (roleLabel) {
        roleLabel.innerText = role.toUpperCase();
        roleLabel.className = `badge ${role.toLowerCase()}`;
    }

    const form = document.getElementById('deleteUserForm');
    form.action = `/admin/user/${id}/delete`;

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeDeleteUserModal() {
    const modal = document.getElementById('deleteUserModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// -------------------------------------------------------------
// DYNAMIC CLIENT-SIDE TOAST CREATOR
// -------------------------------------------------------------
function showDynamicToast(category, message) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${category}`;
    toast.setAttribute('role', 'alert');

    let iconHtml = '<i class="fa-solid fa-circle-info"></i>';
    if (category === 'success') iconHtml = '<i class="fa-solid fa-circle-check"></i>';
    else if (category === 'danger') iconHtml = '<i class="fa-solid fa-circle-exclamation"></i>';
    else if (category === 'warning') iconHtml = '<i class="fa-solid fa-triangle-exclamation"></i>';

    toast.innerHTML = `
        <div class="toast-icon">${iconHtml}</div>
        <div class="toast-content">
            <p class="toast-message">${message}</p>
        </div>
        <button class="toast-close-btn" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    // Auto dismiss after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}
