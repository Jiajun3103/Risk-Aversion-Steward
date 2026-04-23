// ─── ILMU AI (GLM-5.1) Clearance Strategy ────────────────────────────────────
// API key is kept on the backend — this file only calls the backend proxy endpoint.

const AI_RECOMMEND_URL = "http://127.0.0.1:8000/api/ai/recommend";

async function runAIAnalysis() {
    const container = document.getElementById('ai-clearance-container');
    const btn = document.getElementById('ai-run-btn');

    btn.disabled = true;
    btn.textContent = 'Analyzing...';

    container.innerHTML = `
        <div class="col-span-2 text-center py-16 text-slate-400">
            <i class="fas fa-robot text-5xl mb-4 text-builtinCyan"></i>
            <p class="font-bold text-lg mt-4">AI is analyzing your inventory data...</p>
            <p class="text-sm mt-2">Connecting to ILMU GLM-5.1, please wait...</p>
        </div>
    `;

    try {
        const response = await fetch(AI_RECOMMEND_URL, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Server error ${response.status}`);
        }
        const data = await response.json();
        renderAIStrategies(data.strategies, data.source);
    } catch (error) {
        container.innerHTML = `
            <div class="col-span-2 text-center py-12">
                <p class="text-red-500 font-bold text-lg">AI connection failed</p>
                <p class="text-slate-400 text-sm mt-2">${error.message}</p>
                <p class="text-slate-400 text-xs mt-1">Make sure backend (main.py) is running.</p>
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run AI Analysis';
    }
}

function renderAIStrategies(strategies, source) {
    const container = document.getElementById('ai-clearance-container');
    const urgencyStyle = {
        HIGH:   'text-red-600 bg-red-100',
        MEDIUM: 'text-yellow-600 bg-yellow-100',
        LOW:    'text-slate-500 bg-slate-200'
    };

    const sourceLabel = source === 'ilmu-glm-5.1' ? 'ILMU GLM-5.1' : (source || 'local-rules');

    container.innerHTML = `
        <div class="col-span-2 mb-1 flex justify-end">
            <span class="inline-flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold text-slate-500 bg-slate-100 px-3 py-1 rounded">
                Source: ${sourceLabel}
            </span>
        </div>
    ` + strategies.map((s, i) => `
        <div class="bg-slate-50 p-8 rounded border-t-4 ${i === 0 ? 'border-builtinCyan' : 'border-slate-300'} h-full flex flex-col">
            <div class="flex justify-between items-start mb-3">
                <h4 class="text-lg font-black uppercase tracking-tight">Strategy: ${s.strategy_name}</h4>
                <span class="text-xs font-bold px-3 py-1 rounded-full ${urgencyStyle[s.urgency] || urgencyStyle.LOW}">
                    ${s.urgency}
                </span>
            </div>
            <p class="text-xs text-builtinCyan font-bold mb-3">${s.target_sku} — ${s.target_name}</p>
            <p class="text-sm text-slate-600 mb-6 leading-relaxed min-h-[84px]">${s.description}</p>
            <div class="flex justify-between items-center bg-white p-4 rounded shadow-sm mb-3">
                <span class="text-xs font-bold text-slate-400">EXPECTED RECOVERY</span>
                <span class="text-slate-900 font-black">${s.expected_recovery}</span>
            </div>
            <div class="flex justify-between items-center bg-white p-4 rounded shadow-sm mb-6">
                <span class="text-xs font-bold text-slate-400">SUCCESS PROBABILITY</span>
                <span class="${i === 0 ? 'text-builtinCyan' : 'text-slate-700'} font-black">${s.success_probability}</span>
            </div>
            <button
                onclick="executeStrategy('${s.target_sku}', '${s.strategy_name}')"
                class="w-full bg-builtinCyan text-white py-4 font-black uppercase tracking-widest text-xs hover:shadow-lg transition mt-auto">
                Execute Strategy
            </button>
        </div>
    `).join('');
}

function executeStrategy(sku, strategy) {
    const toast = document.getElementById('toast');
    toast.textContent = `✓ Strategy "${strategy}" executed for ${sku}!`;
    toast.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => toast.classList.add('translate-y-20', 'opacity-0'), 3000);
}
