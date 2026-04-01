document.getElementById('mission-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const runBtn = document.getElementById('run-btn');
    const spinner = document.getElementById('spinner');
    const btnText = document.querySelector('.btn-text');
    const errorBox = document.getElementById('error-box');
    
    // UI Loading state
    errorBox.style.display = 'none';
    spinner.style.display = 'block';
    btnText.textContent = 'Calculating...';
    runBtn.disabled = true;

    try {
        const payload = {
            n_motors: parseInt(document.getElementById('n_motors').value) || 4,
            mass_kg: parseFloat(document.getElementById('mass_kg').value) || 2.0,
            tw: parseFloat(document.getElementById('tw').value) || 2.0,
            cells: parseInt(document.getElementById('cells').value) || 6,
            v_nom: parseFloat(document.getElementById('v_nom').value) || null,
            top_n: parseInt(document.getElementById('top_n').value) || 3
        };

        const response = await fetch('/api/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`Server Error: ${response.statusText}`);
        }

        const data = await response.json();
        
        renderTable('table-motors', data.motors, ['manufacturer', 'model', 'kv', 'mass_g', 'score']);
        renderTable('table-escs', data.escs, ['manufacturer', 'model', 'max_current_a', 'mass_g', 'score']);
        renderTable('table-batteries', data.batteries, ['manufacturer', 'model', 'capacity_mah', 'c_rating', 'mass_g']);
        renderTable('table-propellers', data.propellers, ['manufacturer', 'model', 'diameter_in', 'pitch_in', 'mass_g']);

    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = 'block';
    } finally {
        spinner.style.display = 'none';
        btnText.textContent = 'Generate System';
        runBtn.disabled = false;
    }
});

function renderTable(tableId, items, keys) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    tbody.innerHTML = '';

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr class="empty-state"><td colspan="${keys.length}">No suitable matches found.</td></tr>`;
        return;
    }

    items.forEach(item => {
        const tr = document.createElement('tr');
        keys.forEach(key => {
            const td = document.createElement('td');
            let val = item[key];
            if (typeof val === 'number' && !Number.isInteger(val)) {
                val = val.toFixed(2);
            }
            td.textContent = val !== null && val !== undefined ? val : '-';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}
