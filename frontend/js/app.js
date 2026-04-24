// // 后端 API 基础地址
// const API_BASE = "http://127.0.0.1:8000/api";
// let allProducts =[]; 
// let detectedItems =[]; // 存储 AI 扫描发票识别出的产品

// function formatAIResponse(text) {
//     if (!text) return "No analysis available.";
//     return text
//         .replace(/\n/g, '<br>')
//         .replace(/\*\*(.*?)\*\*/g, '<b class="text-builtinBlue font-bold">$1</b>') 
//         .replace(/- (.*?)(<br>|$)/g, '<li class="ml-4 list-disc text-slate-600">$1</li>'); 
// }

// // 1. 刷新库存界面
// async function refreshInventoryUI() {
//     try {
//         const response = await fetch(`${API_BASE}/inventory`);
//         const data = await response.json();
//         allProducts = data; 

//         const container = document.getElementById('stockout-container');
//         if (container) {
//             if (!data || data.length === 0) {
//                 container.innerHTML = "<p class='p-8 text-center text-slate-400'>No data found in database.</p>";
//             } else {
//                 container.innerHTML = data.map((item) => {
//                     const daysLeft = item.daily_sales > 0 ? Math.floor(item.stock / item.daily_sales) : 999;
//                     const isRisk = daysLeft <= 15;
//                     const statusColor = isRisk ? "text-red-500" : "text-builtinCyan";
//                     const riskLabel = isRisk ? "URGENT" : "STABLE";
//                     const location = item.location || 'N/A';

//                     return `
//                     <div class="inventory-card border border-slate-100 p-6 rounded-sm bg-white flex items-center justify-between shadow-sm hover:border-builtinCyan transition" 
//                          data-sku="${item.sku.toLowerCase()}" 
//                          data-name="${item.name.toLowerCase()}"
//                          data-urgent="${isRisk}">
//                         <div>
//                             <p class="text-[10px] font-bold text-slate-400 uppercase">${item.sku} | ${riskLabel}</p>
//                             <h4 class="font-bold text-lg text-builtinBlue">${item.name}</h4>
//                             <p class="text-[9px] text-slate-400 mt-1 font-bold uppercase tracking-widest"><i class="fa-solid fa-location-dot"></i> Location: ${location}</p>
//                         </div>
//                         <div class="flex gap-12 text-center">
//                             <div><p class="text-[10px] text-slate-400 uppercase font-bold">Stock</p><p class="font-bold text-slate-700">${item.stock}</p></div>
//                             <div><p class="text-[10px] text-slate-400 uppercase font-bold">Days Left</p><p class="font-bold ${statusColor}">${daysLeft} Days</p></div>
//                         </div>
//                         <button onclick="viewRisk('${item.sku}', '${item.name}')" class="bg-builtinBlue text-white px-4 py-2 text-[10px] font-black uppercase transition hover:bg-builtinDarkCyan">View Risk</button>
//                     </div>`;
//                 }).join('');
//             }
//         }
//         if (typeof renderActionSkuResults === "function") renderActionSkuResults(data);
//         return data; 
//     } catch (error) { console.error("Backend Error:", error); }
// }

// // 2. 查看单品风险
// async function viewRisk(sku, name) {
//     const modal = document.getElementById("riskModal");
//     const content = document.getElementById("riskAnalysisContent");
//     document.getElementById("modalProductName").innerText = name;
//     document.getElementById("modalSKU").innerText = sku;
//     if (!modal || !content) return;

//     modal.classList.remove("hidden");
//     content.innerHTML = `<div class="animate-pulse py-4">AI Butler is diagnosing risk profile...</div>`;

//     try {
//         const response = await fetch(`${API_BASE}/risk-analysis/${sku}`);
//         const data = await response.json();
//         content.innerHTML = formatAIResponse(data.analysis);
//     } catch (error) { content.innerHTML = `<p class="text-red-500 font-bold">Analysis failed.</p>`; }
// }

// // 3. 基础库存变动
// async function submitStockMove(type, cSku = null, cQty = null) {
//     const sku = cSku || document.getElementById("action-sku").value;
//     const qty = cQty || parseInt(document.getElementById("action-qty").value);

//     if (!sku || isNaN(qty)) { alert("Please select a product and quantity."); return false; }

//     try {
//         const res = await fetch(`${API_BASE}/stock-move`, {
//             method: 'POST',
//             headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ sku, quantity: type === 'OUT' ? -qty : qty, type })
//         });

//         if (res.ok) {
//             refreshInventoryUI();
//             if (document.getElementById('report-container-dashboard')) loadReports();
//             if (document.getElementById('tab-procurement')?.classList.contains('active')) loadProcurementSuggestions();
//             if(!cSku) {
//                 if(document.getElementById('action-sku-search')) document.getElementById('action-sku-search').value = "";
//                 if(document.getElementById('action-sku')) document.getElementById('action-sku').value = "";
//             }
//             return true;
//         }
//     } catch (e) { return false; }
// }

// // 4. AI 清仓策略
// async function runAIRecommend() {
//     const container = document.getElementById('ai-clearance-result');
//     if (!container) return;

//     container.innerHTML = `<div class="col-span-2 flex flex-col items-center justify-center py-12"><div class="animate-spin rounded-full h-10 w-10 border-b-2 border-builtinCyan mb-4"></div><p class="text-xs font-black text-builtinCyan animate-pulse uppercase tracking-widest">AI Agent Analysis In Progress...</p></div>`;

//     try {
//         const res = await fetch(`${API_BASE}/ai/recommend`, { method: 'POST' });
//         const data = await res.json();
//         container.innerHTML = data.strategies.map(s => `
//             <div class="bg-white p-8 rounded border-t-4 border-builtinCyan shadow-xl hover:scale-[1.02] transition-transform">
//                 <div class="flex justify-between items-start mb-4">
//                     <span class="bg-amber-100 text-amber-700 text-[10px] font-black px-2 py-1 rounded uppercase">${s.urgency} Urgency</span>
//                     <span class="text-slate-400 text-xs font-bold">${s.target_sku}</span>
//                 </div>
//                 <h4 class="text-xl font-black text-builtinBlue mb-2 uppercase">${s.strategy_name}</h4>
//                 <p class="text-slate-500 font-bold text-sm mb-4">${s.target_name}</p>
//                 <p class="text-sm text-slate-600 mb-6 leading-relaxed italic border-l-2 border-slate-100 pl-4">"${s.description}"</p>
//                 <div class="grid grid-cols-2 gap-4">
//                     <div class="bg-slate-50 p-4 rounded text-center">
//                         <p class="text-[9px] font-bold text-slate-400 uppercase mb-1">Recovery</p>
//                         <p class="text-lg font-black text-builtinBlue">${s.expected_recovery}</p>
//                     </div>
//                     <div class="bg-slate-50 p-4 rounded text-center">
//                         <p class="text-[9px] font-bold text-slate-400 uppercase mb-1">Success</p>
//                         <p class="text-lg font-black text-builtinCyan">${s.success_probability}</p>
//                     </div>
//                 </div>
//             </div>
//         `).join("");
//     } catch (e) { container.innerHTML = "<p class='col-span-2 text-center text-red-500'>AI Clearance failed to load.</p>"; }
// }

// async function runFullScan() {
//     const data = await refreshInventoryUI();
//     if (!data) return;
//     const riskCount = data.filter(i => (i.daily_sales > 0 ? i.stock/i.daily_sales : 999) <= 15).length;
//     alert(`Scan: ${data.length} SKUs checked. ${riskCount} Risks found. Opening Clearance AI...`);
//     switchTab({ currentTarget: document.querySelector('button[onclick*="tab-clearance"]') }, 'tab-clearance');
// }

// // 5. 🌟 加载供应商列表 (已恢复) 🌟
// async function loadSuppliers() {
//     const container = document.getElementById('supplier-container');
//     if (!container) return;

//     try {
//         const res = await fetch(`${API_BASE}/suppliers`);
//         if(!res.ok) throw new Error("Failed to load");
//         const data = await res.json();
        
//         if(data.length === 0) {
//             container.innerHTML = `<p class="col-span-2 text-slate-400 font-bold">No suppliers found in database.</p>`;
//             return;
//         }

//         container.innerHTML = data.map(s => `
//             <div class="bg-white p-6 border border-slate-100 shadow-sm flex justify-between items-center hover:border-builtinCyan transition">
//                 <div>
//                     <p class="font-black text-builtinBlue uppercase tracking-tight">${s.supplier_name}</p>
//                     <p class="text-[10px] text-slate-400 mt-1 uppercase font-bold">Lead Time: ${s.lead_time} Days | ${s.contact_email}</p>
//                 </div>
//                 <div class="text-right">
//                     <p class="text-xl font-black ${s.risk_score > 70 ? 'text-red-500':'text-builtinCyan'}">${s.risk_score}</p>
//                     <p class="text-[9px] font-bold text-slate-400 uppercase">Risk Score</p>
//                 </div>
//             </div>`).join("");
//     } catch(e) { 
//         container.innerHTML = `<p class="col-span-2 text-red-500 font-bold">Failed to load suppliers.</p>`; 
//     }
// }

// // 6. 采购建议 & Auto Order
// async function loadProcurementSuggestions() {
//     try {
//         const res = await fetch(`${API_BASE}/inventory`);
//         const data = await res.json();
//         const container = document.getElementById('procurement-container');
//         if(!container) return;

//         const list = data.filter(i => i.stock < (i.daily_sales * 15));
//         container.innerHTML = list.length === 0 ? "<p class='p-8 text-center text-slate-400'>All stock levels optimal.</p>" :
//             list.map(i => {
//                 const suggestQty = Math.ceil(i.daily_sales * 30);
//                 return `
//                 <div class="flex items-center justify-between p-6 hover:bg-slate-50 transition border-b border-slate-50 last:border-0">
//                     <div>
//                         <p class="font-bold text-builtinBlue">${i.name}</p>
//                         <p class="text-[10px] text-red-500 font-bold uppercase mt-1">Suggested PO: ${suggestQty} units</p>
//                     </div>
//                     <button onclick="triggerAutoOrder('${i.sku}', '${i.name}', ${suggestQty})" class="bg-builtinCyan text-white px-4 py-2 font-black text-[10px] uppercase hover:bg-builtinDarkCyan transition">Auto Order</button>
//                 </div>`;
//             }).join("");
//     } catch(e){}
// }

// async function triggerAutoOrder(sku, name, qty) {
//     if (!confirm(`[STEP 1/2] Confirm restocking order:\n\nProduct: ${name}\nQuantity: ${qty} units\n\nContinue?`)) return;
//     if (!confirm(`[FINAL WARNING] This will send an official Purchase Order email to the supplier.\n\nAre you sure?`)) return;

//     try {
//         const res = await fetch(`${API_BASE}/order/auto`, {
//             method: 'POST', headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ sku: sku, quantity: qty, type: 'IN' })
//         });
//         if (res.ok) {
//             if(confirm(`✅ Order Sent Successfully!\n\nDid you make a mistake? Click "OK" to CANCEL this order right now.`)) {
//                 await runCancelOrder(sku, name, qty);
//             } else {
//                 refreshInventoryUI();
//                 loadProcurementSuggestions();
//                 loadReports();
//             }
//         } else { alert("❌ Order failed."); }
//     } catch (e) { alert("❌ Network Error."); }
// }

// async function runCancelOrder(sku, name, qty) {
//     if (!confirm(`ARE YOU SURE?\n\nThis will cancel the order for ${name} (${sku}), deduct ${qty} units from stock, and send an URGENT CANCELLATION EMAIL to the supplier.`)) return;
//     try {
//         const res = await fetch(`${API_BASE}/order/cancel`, {
//             method: 'POST', headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ sku: sku, quantity: qty, type: 'OUT' })
//         });
//         if (res.ok) {
//             alert(`🚫 SUCCESS!\n\nOrder for ${sku} cancelled.\nStock adjusted and supplier notified.`);
//             refreshInventoryUI();
//             loadReports();
//             loadProcurementSuggestions();
//         }
//     } catch (e) {}
// }

// // 7. AI 发票扫描仪 (Sales Scanner)
// async function handleInvoiceUpload() {
//     const fileInput = document.getElementById('invoiceFile');
//     if (!fileInput || !fileInput.files[0]) return;

//     const previewArea = document.getElementById('scanner-preview');
//     const listContainer = document.getElementById('scanner-items-list');

//     previewArea.classList.remove('hidden');
//     listContainer.innerHTML = `
//         <div class="bg-white p-12 text-center border border-slate-100 shadow-sm">
//             <div class="animate-spin inline-block w-8 h-8 border-[3px] border-builtinCyan border-t-transparent rounded-full mb-4"></div>
//             <p class="text-xs font-black text-builtinBlue animate-pulse uppercase tracking-widest">Ilmu AI is reading your invoice...</p>
//         </div>`;

//     const formData = new FormData();
//     formData.append('file', fileInput.files[0]);

//     try {
//         const res = await fetch(`${API_BASE}/invoice/analyze`, { method: 'POST', body: formData });
//         const data = await res.json();
//         if (data.error) {
//             listContainer.innerHTML = `<p class="p-8 text-center text-orange-500 font-bold border-2 border-orange-100">${data.error}</p>`;
//             return;
//         }
//         if (data.items && data.items.length > 0) {
//             detectedItems = data.items;
//             listContainer.innerHTML = data.items.map(item => `
//                 <div class="bg-white p-6 border border-slate-100 shadow-sm flex justify-between items-center hover:border-builtinCyan transition">
//                     <div>
//                         <p class="font-black text-builtinBlue text-lg uppercase tracking-tight">${item.name}</p>
//                         <p class="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Matched SKU: ${item.sku}</p>
//                     </div>
//                     <div class="text-right">
//                         <p class="text-2xl font-black text-orange-500">-${item.quantity}</p>
//                         <p class="text-[9px] font-black text-slate-400 uppercase">Sales Quantity</p>
//                     </div>
//                 </div>
//             `).join("");
//         } else {
//             listContainer.innerHTML = `<p class="p-12 text-center text-red-500 font-bold bg-white border border-slate-100">AI could not detect any matching SKUs.</p>`;
//         }
//     } catch (e) { listContainer.innerHTML = `<p class="text-red-500 text-center">Server Error.</p>`; }
// }

// async function confirmBulkOutbound() {
//     if (!confirm(`CAUTION: This will decrease stock for ${detectedItems.length} items. Proceed?`)) return;
//     for (const item of detectedItems) { await submitStockMove('OUT', item.sku, item.quantity); }
//     alert(`✅ SUCCESS: Items processed and stock updated.`);
//     document.getElementById('scanner-preview').classList.add('hidden');
//     document.getElementById('invoiceFile').value = ""; 
//     refreshInventoryUI(); 
// }

// // 8. 报表加载与导出
// async function loadReports() {
//     const containers =[document.getElementById("report-container-dashboard"), document.getElementById("report-container")];
//     try {
//         const res = await fetch(`${API_BASE}/reports`);
//         const data = await res.json();
//         const html = data.map(row => {
//             const canCancel = row.type === 'IN';
//             return `
//             <tr class="hover:bg-slate-50 transition border-b border-slate-50">
//               <td class="p-4 text-xs text-slate-400 font-mono">${new Date(row.timestamp).toLocaleString()}</td>
//               <td class="p-4 font-bold text-builtinBlue">${row.name}<br><span class="text-[10px] text-slate-400">${row.sku}</span></td>
//               <td class="p-4"><span class="px-2 py-1 rounded text-[10px] font-black ${row.type === 'IN' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}">${row.type}</span></td>
//               <td class="p-4 text-right font-bold ${row.quantity < 0 ? 'text-red-500' : 'text-green-600'}">${row.quantity > 0 ? '+' : ''}${row.quantity}</td>
//               <td class="p-4 text-right flex justify-end gap-3">
//                 ${canCancel ? `<button onclick="runCancelOrder('${row.sku}', '${row.name}', ${row.quantity})" title="Cancel Order" class="text-builtinCyan hover:text-builtinDarkCyan transition"><i class="fa-solid fa-rotate-left"></i></button>` : ''}
//                 <button onclick="deleteLog(${row.id})" title="Delete Record" class="text-slate-300 hover:text-red-500 transition"><i class="fa-solid fa-trash-can"></i></button>
//               </td>
//             </tr>`;
//         }).join("");
//         containers.forEach(c => { if(c) c.innerHTML = html; });
//     } catch (e) {}
// }

// async function exportReportToCSV() {
//     try {
//         const res = await fetch(`${API_BASE}/reports`);
//         const data = await res.json();
//         if (!data || data.length === 0) { alert("No data available to export!"); return; }
//         let csvContent = "Transaction ID,Date & Time,SKU,Product Name,Transaction Type,Quantity\n";
//         data.forEach(row => {
//             const safeName = `"${(row.name || 'Unknown').replace(/"/g, '""')}"`;
//             const dateStr = `"${new Date(row.timestamp).toLocaleString()}"`;
//             const qtyStr = row.quantity > 0 ? `+${row.quantity}` : row.quantity;
//             csvContent += `${row.id},${dateStr},${row.sku},${safeName},${row.type},${qtyStr}\n`;
//         });
//         const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
//         const url = URL.createObjectURL(blob);
//         const link = document.createElement("a");
//         link.setAttribute("href", url);
//         link.setAttribute("download", `Inventory_Report_${new Date().toISOString().slice(0,10)}.csv`);
//         document.body.appendChild(link); link.click(); document.body.removeChild(link);
//     } catch (e) {}
// }

// async function deleteLog(id) {
//     if(!confirm("Delete record?")) return;
//     try { await fetch(`${API_BASE}/transactions/${id}`, { method: 'DELETE' }); loadReports(); } catch (e) {}
// }

// // 9. 视图与页面切换逻辑 (修复了 Suppliers 无法显示的问题) 🌟
// function showView(view) {
//     // 处理视图显示与隐藏 (安全检查)
//     const views = ['dashboard', 'suppliers', 'reports'];
//     views.forEach(v => {
//         const el = document.getElementById(`view-${v}`);
//         if(el) el.style.display = (v === view) ? 'block' : 'none';
//     });

//     // 导航栏高亮
//     document.querySelectorAll('.nav-link').forEach(link => {
//         link.classList.remove('text-builtinCyan');
//         if(link.innerText.toLowerCase() === view.toLowerCase()) link.classList.add('text-builtinCyan');
//     });

//     // 加载数据
//     if(view === 'suppliers') {
//         loadSuppliers();
//     } else if(view === 'dashboard') {
//         refreshInventoryUI();
//     } else if(view === 'reports') {
//         loadReports();
//     }
// }

// function switchTab(evt, tabId) {
//     const contents = document.getElementsByClassName("tab-content");
//     for (let i = 0; i < contents.length; i++) contents[i].classList.remove("active");
//     const tabs = evt.currentTarget.parentNode.getElementsByTagName("button");
//     for (let i = 0; i < tabs.length; i++) tabs[i].classList.remove("tab-active");
    
//     document.getElementById(tabId).classList.add("active");
//     evt.currentTarget.classList.add("tab-active");

//     if (tabId === 'tab-reports') loadReports();
//     if (tabId === 'tab-procurement') loadProcurementSuggestions();
//     if (tabId === 'tab-clearance') runAIRecommend();
// }

// function closeRiskModal() { document.getElementById("riskModal").classList.add("hidden"); }

// async function applyFixStock() {
//     const success = await submitStockMove('IN', document.getElementById("modalSKU").innerText, parseInt(document.getElementById("modal-qty").value));
//     if (success) closeRiskModal();
// }

// // 页面加载自动执行
// document.addEventListener('DOMContentLoaded', () => {
//     refreshInventoryUI();
// });