// 指向你的 FastAPI 后端
const API_URL = "http://127.0.0.1:8000/api/inventory";

async function refreshInventoryUI() {
    try {
        const response = await fetch(API_URL);
        const data = await response.json();

        const container = document.getElementById('stockout-container');
        
        if (!data || data.length === 0) {
            container.innerHTML = "<p class='p-8 text-center text-slate-400'>No data found in database.</p>";
            return;
        }

        // 开始渲染数据库内容
        container.innerHTML = data.map((item, index) => {
            
            // --- 核心逻辑：计算剩余天数 ---
            // 如果日销为0，则显示 999 天（无风险）
            const daysLeft = item.daily_sales > 0 ? Math.floor(item.stock / item.daily_sales) : 999;
            
            // 避险型管家规则：少于 15 天标红，否则标青色
            const isRisk = daysLeft <= 15;
            const statusColor = isRisk ? "text-red-500" : "text-builtinCyan";
            const riskLabel = isRisk ? "URGENT" : "STABLE";

            return `
            <div class="border border-slate-100 p-6 rounded-sm hover:border-builtinCyan transition flex items-center justify-between bg-white shadow-sm">
                <div class="flex gap-6 items-center">
                    <div class="w-12 h-12 bg-slate-50 rounded flex items-center justify-center text-builtinBlue font-bold">#${index + 1}</div>
                    <div>
                        <p class="text-[10px] font-bold uppercase ${isRisk ? 'text-red-400' : 'text-slate-400'}">
                            ${item.sku} | ${riskLabel}
                        </p>
                        <h4 class="font-bold text-lg text-builtinBlue">${item.name}</h4>
                    </div>
                </div>
                
                <div class="grid grid-cols-3 gap-12 text-center">
                    <div>
                        <p class="text-[10px] text-slate-400 uppercase font-bold">Stock</p>
                        <p class="font-bold text-slate-700">${item.stock}</p>
                    </div>
                    <div>
                        <p class="text-[10px] text-slate-400 uppercase font-bold">Daily Sale</p>
                        <p class="font-bold text-slate-700">${item.daily_sales}</p>
                    </div>
                    <div>
                        <p class="text-[10px] text-slate-400 uppercase font-bold">Days Left</p>
                        <p class="font-bold ${statusColor}">${daysLeft} Days</p>
                    </div>
                </div>

                <div class="flex gap-2">
                    <button onclick="generatePO('${item.sku}')" class="bg-builtinBlue text-white px-6 py-3 font-bold text-xs uppercase rounded-sm hover:bg-builtinDarkCyan transition">
                        Create Auto PO
                    </button>
                </div>
            </div>
            `;
        }).join('');

    } catch (error) {
        console.error("Backend Error:", error);
        document.getElementById('stockout-container').innerHTML = 
            `<p class="text-red-500 p-8 text-center font-bold">Backend connection failed. Make sure main.py is running.</p>`;
    }
}

// 模拟采购单生成
function generatePO(sku) {
    alert(`[Automation] PO generated for ${sku}. Connecting to supplier...`);
}

// 页面加载完成后立即运行
document.addEventListener('DOMContentLoaded', refreshInventoryUI);