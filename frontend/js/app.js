// 后端 API 基础地址
const API_BASE = "http://127.0.0.1:8000/api";

/**
 * 1. 刷新库存界面 & 更新产品下拉列表
 * 更新点：增加了库位 (Location) 显示
 */
async function refreshInventoryUI() {
    try {
        const response = await fetch(`${API_BASE}/inventory`);
        const data = await response.json();

        const container = document.getElementById('stockout-container');
        if (container) {
            if (!data || data.length === 0) {
                container.innerHTML = "<p class='p-8 text-center text-slate-400'>No data found in database.</p>";
            } else {
                container.innerHTML = data.map((item, index) => {
                    const daysLeft = item.daily_sales > 0 ? Math.floor(item.stock / item.daily_sales) : 999;
                    const isRisk = daysLeft <= 15;
                    const statusColor = isRisk ? "text-red-500" : "text-builtinCyan";
                    const riskLabel = isRisk ? "URGENT" : "STABLE";
                    // 获取库位，如果没有则显示 N/A
                    const location = item.location || 'N/A';

                    return `
                    <div class="inventory-card border border-slate-100 p-6 rounded-sm bg-white flex items-center justify-between shadow-sm hover:border-builtinCyan transition" 
                         data-sku="${item.sku.toLowerCase()}" 
                         data-name="${item.name.toLowerCase()}"
                         data-urgent="${isRisk}">
                        <div>
                            <p class="text-[10px] font-bold text-slate-400 uppercase">${item.sku} | ${riskLabel}</p>
                            <h4 class="font-bold text-lg text-builtinBlue">${item.name}</h4>
                            <p class="text-[9px] text-slate-400 mt-1 font-bold"><i class="fa-solid fa-location-dot"></i> LOCATION: ${location}</p>
                        </div>
                        <div class="flex gap-12 text-center">
                            <div><p class="text-[10px] text-slate-400 uppercase font-bold">Stock</p><p class="font-bold text-slate-700">${item.stock}</p></div>
                            <div><p class="text-[10px] text-slate-400 uppercase font-bold">Days Left</p><p class="font-bold ${statusColor}">${daysLeft} Days</p></div>
                        </div>
                        <button onclick="viewRisk('${item.sku}', '${item.name}')" class="bg-builtinBlue text-white px-4 py-2 text-[10px] font-black uppercase hover:bg-builtinDarkCyan transition">
                            View Risk
                        </button>
                    </div>`;
                }).join('');
            }
        }

        const selectElement = document.getElementById('action-sku');
        if (selectElement) {
            selectElement.innerHTML = data.map(item => 
                `<option value="${item.sku}">${item.name} (${item.sku})</option>`
            ).join('');
        }

        return data; 

    } catch (error) {
        console.error("Backend Error:", error);
    }
}

/**
 * 功能：搜索与过滤 (Search & Filter)
 */
function filterInventory() {
    const term = document.getElementById("skuSearch") ? document.getElementById("skuSearch").value.toLowerCase() : "";
    const showOnlyUrgent = document.getElementById("urgentFilter") ? document.getElementById("urgentFilter").checked : false;
    const cards = document.querySelectorAll(".inventory-card");

    cards.forEach(card => {
        const sku = card.getAttribute("data-sku");
        const name = card.getAttribute("data-name");
        const isUrgent = card.getAttribute("data-urgent") === "true";

        const matchesSearch = sku.includes(term) || name.includes(term);
        const matchesUrgent = showOnlyUrgent ? isUrgent : true;

        if (matchesSearch && matchesUrgent) {
            card.style.display = "flex";
        } else {
            card.style.display = "none";
        }
    });
}

/**
 * 2. 查看单个产品风险分析
 */
async function viewRisk(sku, name) {
    const modal = document.getElementById("riskModal");
    const content = document.getElementById("riskAnalysisContent");
    const productNameLabel = document.getElementById("modalProductName");
    const skuLabel = document.getElementById("modalSKU");

    if (!modal || !content) return;
    productNameLabel.innerText = name;
    skuLabel.innerText = sku;

    modal.classList.remove("hidden");
    content.innerHTML = `<div class="flex flex-col items-center justify-center py-10"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-builtinCyan mb-4"></div><p class="text-[10px] font-bold text-builtinCyan uppercase animate-pulse">Gathering Evidence...</p></div>`;

    try {
        const response = await fetch(`${API_BASE}/risk-analysis/${sku}`);
        const data = await response.json();
        if (data.analysis) {
            const formattedText = data.analysis.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<b>$1</b>'); 
            content.innerHTML = `<div class="text-slate-700 font-medium leading-relaxed italic border-l-4 border-builtinCyan pl-4">${formattedText}</div>`;
        }
    } catch (error) { content.innerHTML = `<p class="text-red-500">Error.</p>`; }
}

function closeRiskModal() {
    const modal = document.getElementById("riskModal");
    if (modal) modal.classList.add("hidden");
}

/**
 * 3. 提交进出货登记
 */
async function submitStockMove(type, customSku = null, customQty = null) {
    const sku = customSku || document.getElementById("action-sku").value;
    const qtyInput = document.getElementById("action-qty");
    const qty = customQty || parseInt(qtyInput.value);

    if (!sku || isNaN(qty) || qty <= 0) {
        alert("Invalid input.");
        return false;
    }
    const finalQty = type === 'OUT' ? -qty : qty;

    try {
        const response = await fetch(`${API_BASE}/stock-move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku, quantity: finalQty, type })
        });

        if (response.ok) {
            refreshInventoryUI(); 
            if (document.getElementById('tab-reports').classList.contains('active')) loadReports();
            return true;
        }
    } catch (error) { alert("Offline."); return false; }
}

async function applyFixStock() {
    const sku = document.getElementById("modalSKU").innerText;
    const qty = parseInt(document.getElementById("modal-qty").value);
    const success = await submitStockMove('IN', sku, qty);
    if (success) { alert("Restocked!"); closeRiskModal(); }
}

/**
 * 功能：Live Risk Scan (全系统扫描)
 */
async function runFullScan() {
    const data = await refreshInventoryUI();
    if (!data) return;
    const highRiskItems = data.filter(item => (item.daily_sales > 0 ? item.stock / item.daily_sales : 999) <= 15);
    alert(`System Scan Complete!\nSKUs Analysed: ${data.length}\nCritical Alerts: ${highRiskItems.length}`);
    switchTab({ currentTarget: document.querySelector('button[onclick*="tab-prediction"]') }, 'tab-prediction');
    runAIPrediction();
}

/**
 * 功能：导出报表为 CSV (Export CSV)
 */
function exportReportToCSV() {
    const table = document.getElementById("report-container");
    const rows = table.querySelectorAll("tr");
    if (rows.length === 0 || rows[0].innerText.includes("No history")) {
        alert("No data to export");
        return;
    }

    let csvContent = "data:text/csv;charset=utf-8,Timestamp,Product,Type,Quantity\n";
    rows.forEach(row => {
        const cols = row.querySelectorAll("td");
        const data = Array.from(cols).map(c => c.innerText.replace(/\n/g, " ")).join(",");
        csvContent += data + "\n";
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Inventory_Activity_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * 功能：加载供应商 Dashboard (Suppliers)
 */
async function loadSuppliers() {
    const container = document.getElementById('supplier-container');
    if (!container) return;

    try {
        // 假设后端有 /api/suppliers 接口
        const response = await fetch(`${API_BASE}/inventory`); // 演示用，暂借用 inventory 数据
        const data = await response.json(); 
        
        container.innerHTML = `
            <div class="bg-white border border-slate-100 p-6">
                <p class="text-xs font-bold text-slate-400 mb-4 uppercase">Connected Supply Chain</p>
                <div class="space-y-4">
                    <div class="flex justify-between items-center p-4 bg-slate-50 rounded">
                        <div><p class="font-bold">Xinda Tech</p><p class="text-[10px] text-slate-400">Lead Time: 7 Days</p></div>
                        <div class="text-right"><p class="text-orange-500 font-black">85/100</p><p class="text-[10px] uppercase font-bold text-slate-400 text-nowrap">Risk Score</p></div>
                    </div>
                </div>
            </div>`;
    } catch (e) { console.error(e); }
}

/**
 * 功能：加载智能采购建议 (Procurement Suggestions)
 */
async function loadProcurementSuggestions() {
    const container = document.getElementById('procurement-container');
    if (!container) return;

    try {
        const response = await fetch(`${API_BASE}/inventory`);
        const data = await response.json();
        
        // 过滤出需要补货的项目：库存 < (日销 * 15天预警)
        const suggestions = data.filter(item => item.stock < (item.daily_sales * 15));

        if(suggestions.length === 0) {
            container.innerHTML = "<p class='p-8 text-center text-slate-400'>Stock levels healthy. No urgent procurement needed.</p>";
            return;
        }

        container.innerHTML = suggestions.map(item => `
            <div class="flex items-center justify-between p-4 border-b border-slate-100">
                <div>
                    <p class="font-bold text-builtinBlue">${item.name}</p>
                    <p class="text-[10px] text-red-500 font-bold uppercase tracking-widest">Suggested Buy: ${Math.ceil(item.daily_sales * 30)} units</p>
                </div>
                <button onclick="submitStockMove('IN', '${item.sku}', ${Math.ceil(item.daily_sales * 30)})" class="text-[10px] font-black bg-builtinCyan text-white px-3 py-1 uppercase">Auto Order</button>
            </div>
        `).join("");
    } catch (e) { console.error(e); }
}

/**
 * 5. 加载进出货报表
 */
async function loadReports() {
    const container = document.getElementById('report-container');
    if (!container) return;
    try {
        const response = await fetch(`${API_BASE}/reports`);
        const data = await response.json();
        if (data.length === 0) {
            container.innerHTML = "<tr><td colspan='5' class='p-8 text-center text-slate-400'>No history.</td></tr>";
            return;
        }
        container.innerHTML = data.map(row => `
            <tr>
              <td class="p-4 text-xs text-slate-400 font-mono">${row.timestamp}</td>
              <td class="p-4 font-bold text-builtinBlue">${row.name}<br><span class="text-[10px] text-slate-400 font-normal uppercase">${row.sku}</span></td>
              <td class="p-4"><span class="px-2 py-1 rounded text-[10px] font-black ${row.type === 'IN' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}">${row.type}</span></td>
              <td class="p-4 text-right font-bold ${row.quantity < 0 ? 'text-red-500' : 'text-green-600'}">${row.quantity > 0 ? '+' : ''}${row.quantity}</td>
              <td class="p-4 text-right"><button onclick="deleteLog(${row.id})" class="text-slate-300 hover:text-red-500"><i class="fa-solid fa-trash-can"></i></button></td>
            </tr>
        `).join("");
    } catch (e) { console.error(e); }
}

async function deleteLog(id) {
    if (!confirm(`Delete record ID: ${id}?`)) return;
    try {
        await fetch(`${API_BASE}/transactions/${id}`, { method: 'DELETE' });
        loadReports();
    } catch (error) { alert("Error."); }
}

/**
 * 6. AI 销量预测
 */
async function runAIPrediction() {
    const resultBox = document.getElementById("ai-prediction-result");
    if (!resultBox) return;
    resultBox.innerHTML = `<div class="flex flex-col items-center justify-center py-12"><div class="animate-spin rounded-full h-10 w-10 border-b-2 border-builtinCyan mb-4"></div><p class="text-xs font-bold text-builtinCyan animate-pulse">AI ANALYZING...</p></div>`;
    try {
        const response = await fetch(`${API_BASE}/predict`);
        const data = await response.json();
        const formattedText = data.prediction.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<b>$1</b>'); 
        resultBox.innerHTML = `<div class="prose prose-slate max-w-none text-slate-700 font-medium italic border-l-4 border-builtinCyan pl-4">${formattedText}</div>`;
    } catch (error) { resultBox.innerHTML = `<p class="text-red-500">Failed.</p>`; }
}

/**
 * 辅助：Tab 切换
 */
function switchTab(evt, tabId) {
    const contents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < contents.length; i++) contents[i].classList.remove("active");
    const tabs = evt.currentTarget.parentNode.getElementsByTagName("button");
    for (let i = 0; i < tabs.length; i++) tabs[i].classList.remove("tab-active");
    document.getElementById(tabId).classList.add("active");
    evt.currentTarget.classList.add("tab-active");
    
    // Tab 专属加载逻辑
    if(tabId === 'tab-suppliers') loadSuppliers();
    if(tabId === 'tab-procurement') loadProcurementSuggestions();
}

/**
 * 初始化
 */
document.addEventListener('DOMContentLoaded', () => {
    refreshInventoryUI();
});