const socket = io();

const role = localStorage.getItem('userRole') || 'Guest';

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('userRoleBadge').innerText = role;

    if (role === 'Admin') {
        document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
        document.getElementById('admin-stats-grid').classList.remove('hidden');
        fetchStats();
    }
    
    if (role === 'Admin' || role === 'Receptionist') {
        document.querySelectorAll('.staff-only').forEach(el => el.classList.remove('hidden'));
        fetchKitchenOrders();
    }

    if (role === 'Guest') {
        document.querySelectorAll('.guest-only').forEach(el => el.classList.remove('hidden'));
        fetchInvoices();
        fetchFood();
    }

    fetchRooms();
    fetchBookings();
    
    // Live Event Listeners
    socket.on('notification', data => {
        showToast(data.message, 'info');
        appendLiveFeed(data.message);
        if (role === 'Admin') fetchStats();
        if (role === 'Admin' || role === 'Receptionist') fetchKitchenOrders();
        fetchBookings();
    });

    socket.on('room_update', data => {
        // Optimistic refresh
        fetchRooms();
        if (role === 'Admin') fetchStats();
    });
});

function switchView(view) {
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    document.getElementById(`nav-${view}`).classList.add('active');

    const sections = document.querySelectorAll('.view-section');
    sections.forEach(el => {
        if (!el.classList.contains('hidden')) {
            el.classList.add('fade-out');
            setTimeout(() => {
                el.classList.add('hidden');
                el.classList.remove('fade-out');
            }, 300);
        }
    });
    
    setTimeout(() => {
        const target = document.getElementById(`view-${view}`);
        target.classList.remove('hidden');
        void target.offsetWidth;
        target.classList.add('fade-in');
    }, 300);
}

function logout() {
    fetch('/api/auth/logout', { method: 'POST' }).then(() => {
        localStorage.clear();
        window.location.href = '/login?logout=1';
    });
}

// --- Rooms ---
async function fetchRooms() {
    const res = await fetch('/api/rooms');
    const rooms = await res.json();
    renderRooms(rooms);
    populateRoomSelect(rooms);
}

function renderRooms(rooms) {
    const grid = document.getElementById('rooms-grid');
    grid.innerHTML = '';
    
    rooms.forEach(room => {
        const bdg = `badge-${room.status.toLowerCase()}`;
        grid.innerHTML += `
            <div class="glass-card">
                <h3>Room ${room.number}</h3>
                <p class="text-muted">${room.type} - ₹${room.price}/night</p>
                <div class="mt-1 badge ${bdg}">${room.status}</div>
                ${(role === 'Admin' || role === 'Receptionist') ? 
                  `<button class="btn btn-secondary mt-2" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;" onclick="deleteRoom(${room.id})">Delete</button>` 
                  : ''}
            </div>
        `;
    });
}

function populateRoomSelect(rooms) {
    const select = document.getElementById('book-room-id');
    const prevVal = select.value;
    select.innerHTML = '<option value="">Select Room...</option>';
    rooms.forEach(room => {
        // Only show available rooms for booking, but allow all maybe? Real system would filter.
        if(room.status === 'Available') {
            select.innerHTML += `<option value="${room.id}">Room ${room.number} (${room.type} - ₹${room.price}/n)</option>`;
        }
    });
    // try restore
    if(prevVal) select.value = prevVal;
}

function toggleAddRoomModal() {
    document.getElementById('add-room-modal').classList.toggle('hidden');
}

async function addRoom() {
    const number = document.getElementById('new-room-number').value;
    const type = document.getElementById('new-room-type').value;
    const price = document.getElementById('new-room-price').value;

    const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ number, type, price: parseFloat(price) })
    });
    if(res.ok) {
        showToast('Room added successfully');
        toggleAddRoomModal();
    } else {
        const err = await res.json();
        showToast(err.error || 'Setup failed', 'error');
    }
}

async function deleteRoom(id) {
    if(confirm('Are you sure?')) {
        await fetch(`/api/rooms/${id}`, { method: 'DELETE' });
    }
}

// --- Bookings ---
async function fetchBookings() {
    const res = await fetch('/api/bookings');
    const bookings = await res.json();
    renderBookings(bookings);
}

function renderBookings(bookings) {
    const grid = document.getElementById('bookings-grid');
    grid.innerHTML = '';
    
    bookings.forEach(b => {
        const start = new Date(b.start_date).toLocaleDateString();
        const end = new Date(b.end_date).toLocaleDateString();
        
        let actions = '';
        if (role === 'Admin' || role === 'Receptionist') {
            if (b.status === 'Confirmed') {
                actions = `<button class="btn btn-success mt-1" style="width:100%;" onclick="checkIn(${b.id})">Check In</button>`;
            } else if (b.status === 'Checked-In') {
                actions = `<button class="btn btn-primary mt-1" style="width:100%;" onclick="checkOut(${b.id})">Check Out & Bill</button>`;
            }
        }

        grid.innerHTML += `
            <div class="glass-card">
                <h4>Booking #${b.id}</h4>
                <p>Room ID: ${b.room_id}</p>
                <p class="text-muted">${start} to ${end}</p>
                <p class="text-muted" style="margin-top: 0.5rem; font-weight: 500;">Payment via: ${b.payment_type || 'Card'}</p>
                <div class="mt-1 badge badge-${b.status.toLowerCase()}">${b.status}</div>
                ${actions}
            </div>
        `;
    });
}

async function createBooking() {
    const start_date = document.getElementById('book-start').value;
    const end_date = document.getElementById('book-end').value;
    const room_id = document.getElementById('book-room-id').value;
    const payment_type = document.getElementById('book-payment-type').value;

    if (!start_date || !end_date || !room_id || !payment_type) {
        return showToast('Please fill all fields', 'error');
    }

    const res = await fetch('/api/bookings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_date, end_date, room_id: parseInt(room_id), payment_type })
    });
    
    const data = await res.json();
    if(res.ok) {
        showToast('Booking Confirmed!', 'success');
        fetchBookings();
    } else {
        showToast(data.error, 'error');
    }
}

async function checkIn(id) {
    const res = await fetch(`/api/bookings/${id}/checkin`, { method: 'POST' });
    if(res.ok) showToast('Guest checked in');
}

async function checkOut(id) {
    const res = await fetch(`/api/bookings/${id}/checkout`, { method: 'POST' });
    const data = await res.json();
    if(res.ok) {
        showToast(`Checkout complete. Bill: ₹${data.total.toFixed(2)} (inc. 10% tax)`, 'success');
        // Wait and show a second toast for invoice
        setTimeout(() => showToast('Invoice Generated!', 'info'), 1500);
    }
}

// --- Admin ---
let currentRevenueData = { today: 0, weekly: 0, monthly: 0 };

function setRevenueTab(tab) {
    const display = document.getElementById('stat-revenue-display');
    const label = document.getElementById('active-revenue-label');
    if (!display) return;
    
    if (tab === 'today') {
        label.innerText = "Today's Revenue";
        display.innerText = '₹' + currentRevenueData.today.toLocaleString('en-IN', {minimumFractionDigits: 2});
    } else if (tab === 'weekly') {
        label.innerText = "Weekly Revenue";
        display.innerText = '₹' + currentRevenueData.weekly.toLocaleString('en-IN', {minimumFractionDigits: 2});
    } else if (tab === 'monthly') {
        label.innerText = "Monthly Revenue";
        display.innerText = '₹' + currentRevenueData.monthly.toLocaleString('en-IN', {minimumFractionDigits: 2});
    }
}

async function fetchStats() {
    const res = await fetch('/api/admin/stats');
    if(res.ok) {
        const data = await res.json();
        currentRevenueData = {
            today: Number(data.revenue_today),
            weekly: Number(data.revenue_weekly),
            monthly: Number(data.revenue_monthly)
        };
        setRevenueTab('today');
        document.getElementById('stat-bookings').innerText = data.today_bookings;
        document.getElementById('stat-available').innerText = data.available;
        document.getElementById('stat-occupied').innerText = data.occupied;
    }
}

async function createStaff() {
    const name = document.getElementById('staff-name').value;
    const email = document.getElementById('staff-email').value;
    const password = document.getElementById('staff-password').value;
    const role = document.getElementById('staff-role').value;

    if (!name || !email || !password) {
        return showToast('Please fill all fields', 'error');
    }

    try {
        const res = await fetch('/api/admin/staff', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, role })
        });
        const data = await res.json();
        
        if (res.ok) {
            showToast(data.message, 'success');
            document.getElementById('staff-name').value = '';
            document.getElementById('staff-email').value = '';
            document.getElementById('staff-password').value = '';
        } else {
            showToast(data.error, 'error');
        }
    } catch (err) {
        showToast('Connection error', 'error');
    }
}

// --- Invoices & Food (Guest) ---
async function fetchInvoices() {
    const res = await fetch('/api/user/invoices');
    if(res.ok) {
        const invoices = await res.json();
        const grid = document.getElementById('invoices-grid');
        grid.innerHTML = invoices.length ? '' : '<p class="text-muted">No invoices found.</p>';
        invoices.forEach(i => {
            const date = new Date(i.date).toLocaleDateString();
            grid.innerHTML += `
                <div class="glass-card">
                    <h3>Invoice #${i.id}</h3>
                    <p class="text-muted">Date: ${date}</p>
                    <hr style="border:0; border-top:1px solid var(--glass-border); margin:0.5rem 0;" />
                    <p>Room: ${i.room}</p>
                    <p>Room Charges: ₹${i.room_charges.toFixed(2)}</p>
                    <p>Extra Charges: ₹${i.extra_charges.toFixed(2)}</p>
                    <p>Taxes (10%): ₹${(i.taxes || 0).toFixed(2)}</p>
                    <h3 class="mt-1" style="color:var(--accent-color)">Total: ₹${i.total.toFixed(2)}</h3>
                </div>
            `;
        });
    }
}

async function fetchFood() {
    const res = await fetch('/api/food');
    if(res.ok) {
        const foods = await res.json();
        const grid = document.getElementById('food-menu-grid');
        grid.innerHTML = '';
        foods.forEach(f => {
            const img = f.image_url ? `<img src="${f.image_url}" style="width:100%; height:150px; object-fit:cover; border-radius:4px 4px 0 0;">` : '';
            grid.innerHTML += `
                <div class="glass-card" style="padding:0; overflow:hidden;">
                    ${img}
                    <div style="padding: 1.5rem;">
                        <h3>${f.name}</h3>
                        <p class="text-muted">${f.description}</p>
                        <h3 class="mt-1" style="color:var(--accent-color);">₹${f.price.toFixed(2)}</h3>
                        <button class="btn btn-primary mt-1" style="width:100%" onclick="orderFood(${f.id})">Order to Room</button>
                    </div>
                </div>
            `;
        });
    }
}

async function orderCustomFood() {
    const custom_request = document.getElementById('custom-food-request').value;
    if(!custom_request) { return showToast('Please enter your custom request.', 'error'); }
    const res = await fetch('/api/food/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_request, quantity: 1 })
    });
    const data = await res.json();
    if(res.ok) { 
        showToast(data.message, 'success'); 
        document.getElementById('custom-food-request').value = '';
    }
    else { showToast(data.error, 'error'); }
}

async function orderFood(food_id) {
    const res = await fetch('/api/food/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ food_id, quantity: 1 })
    });
    const data = await res.json();
    if(res.ok) { showToast(data.message, 'success'); }
    else { showToast(data.error, 'error'); }
}

// --- Kitchen Orders (Staff) ---
async function fetchKitchenOrders() {
    const res = await fetch('/api/admin/food_orders');
    if(res.ok) {
        const orders = await res.json();
        const grid = document.getElementById('kitchen-orders-grid');
        grid.innerHTML = orders.length ? '' : '<p class="text-muted">No pending orders.</p>';
        orders.forEach(o => {
            let btn = '';
            if (o.status === 'Pending') {
                btn = `<button class="btn btn-primary mt-1" style="width:100%" onclick="acceptOrder(${o.id})">Accept Order</button>`;
            } else if (o.status === 'Accepted') {
                btn = `<button class="btn btn-success mt-1" style="width:100%" onclick="deliverOrder(${o.id})">Mark Delivered</button>`;
            }
            const imgHtml = o.image ? `<img src="${o.image}" style="width:100px; height:100px; object-fit:cover; border-radius:8px; flex-shrink:0;">` : `<div style="width:100px; height:100px; background:#f0f0f0; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><span class="text-muted">Custom</span></div>`;
            
            grid.innerHTML += `
                <div class="glass-card" style="display: flex; gap: 1rem; align-items: center; padding: 1rem;">
                    ${imgHtml}
                    <div style="flex-grow: 1;">
                        <h3 style="margin:0;">Room ${o.room}</h3>
                        <p class="text-muted" style="margin: 0.2rem 0;">Order #${o.id}</p>
                        <p style="font-size:1.1rem; font-weight:bold; margin:0.2rem 0;">${o.quantity}x ${o.food}</p>
                        <p style="font-weight:600; color:var(--navy); margin:0;">Total: ₹${o.total.toFixed(2)}</p>
                    </div>
                    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.5rem; min-width: 130px;">
                        <div class="badge badge-${o.status.toLowerCase()}" style="margin:0;">${o.status}</div>
                        ${btn}
                    </div>
                </div>
            `;
        });
    }
}

async function acceptOrder(id) {
    const res = await fetch(`/api/admin/food_orders/${id}/accept`, { method: 'POST' });
    if(res.ok) {
        showToast('Order Accepted & Preparing', 'success');
        fetchKitchenOrders();
    }
}

async function deliverOrder(id) {
    const res = await fetch(`/api/admin/food_orders/${id}/deliver`, { method: 'POST' });
    if(res.ok) {
        showToast('Marked as delivered', 'success');
        fetchKitchenOrders();
    }
}

// Ensure init checks new views
async function submitReview() {
    const rating = document.getElementById('review-rating').value;
    const comment = document.getElementById('review-comment').value;

    if (!comment.trim()) {
        return showToast('Please write a short comment!', 'error');
    }

    const res = await fetch('/api/reviews', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating, comment })
    });
    
    const data = await res.json();
    if(res.ok) {
        showToast(data.message, 'success');
        document.getElementById('review-comment').value = '';
    } else {
        showToast(data.error, 'error');
    }
}

// --- UI Helpers ---
function showToast(msg, type='info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function appendLiveFeed(msg) {
    const feed = document.getElementById('live-feed');
    if(feed.innerText.includes('Waiting')) feed.innerHTML = '';
    
    // Add time
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.innerHTML = `<span style="color:var(--primary-color)">[${time}]</span> ${msg}`;
    entry.style.padding = '0.5rem 0';
    entry.style.borderBottom = '1px solid var(--glass-border)';
    
    feed.prepend(entry);
}
