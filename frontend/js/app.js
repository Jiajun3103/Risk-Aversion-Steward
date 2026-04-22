const API_BASE_URL = "http://127.0.0.1:8000/api";
const SESSION_KEY = "stewardSession";
const NAME_KEY = "stewardName";

let reportsChart = null;

function getSession() {
    try {
        return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    } catch (error) {
        return null;
    }
}

function requireLogin() {
    const session = getSession();
    if (!session || !session.isLoggedIn) {
        window.location.href = "login.html";
        return false;
    }
    return true;
}

async function fetchJson(path) {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
}

async function loadInventoryFromDB() {
    const container = document.getElementById("stockout-container");
    if (!container) {
        return;
    }

    try {
        const data = await fetchJson("/inventory");

        if (!data || data.length === 0) {
            container.innerHTML = "<p class='p-8 text-center text-slate-400'>No data found in database.</p>";
            return;
        }

        container.innerHTML = data.map((item, index) => {
            const daysLeft = item.daily_sales > 0 ? Math.floor(item.stock / item.daily_sales) : 999;
            const isRisk = daysLeft <= 15;
            const statusColor = isRisk ? "text-red-500" : "text-builtinCyan";
            const riskLabel = isRisk ? "URGENT" : "STABLE";

            return `
            <div class="border border-slate-100 p-6 rounded-sm hover:border-builtinCyan transition flex items-center justify-between bg-white shadow-sm">
                <div class="flex gap-6 items-center">
                    <div class="w-12 h-12 bg-slate-50 rounded flex items-center justify-center text-builtinBlue font-bold">#${index + 1}</div>
                    <div>
                        <p class="text-[10px] font-bold uppercase ${isRisk ? "text-red-400" : "text-slate-400"}">
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
        }).join("");
    } catch (error) {
        console.error("Backend Error:", error);
        container.innerHTML = "<p class='text-red-500 p-8 text-center font-bold'>Backend connection failed. Make sure main.py is running.</p>";
    }
}

async function loadSuppliers() {
    const container = document.getElementById("suppliers-container");
    if (!container) {
        return;
    }

    try {
        const suppliers = await fetchJson("/suppliers");
        if (!suppliers || suppliers.length === 0) {
            container.innerHTML = "<tr><td colspan='3' class='p-6 text-center text-slate-400'>No supplier data found.</td></tr>";
            return;
        }

        container.innerHTML = suppliers.map((supplier) => `
            <tr>
                <td class="p-4">
                    <p class="font-bold text-builtinBlue">${supplier.supplier_name}</p>
                </td>
                <td class="p-4 text-slate-600">${supplier.contact_email || "N/A"}</td>
                <td class="p-4 text-builtinCyan font-bold">${supplier.supplied_item_count}</td>
            </tr>
        `).join("");
    } catch (error) {
        console.error("Supplier Error:", error);
        container.innerHTML = "<tr><td colspan='3' class='p-6 text-center text-red-500 font-bold'>Unable to load suppliers.</td></tr>";
    }
}

function updateReportCards(summary) {
    const mapping = {
        "report-total-skus": summary.total_skus,
        "report-low-stock": summary.low_stock_count,
        "report-slow-moving": summary.slow_moving_count,
        "report-supplier-count": summary.supplier_count,
    };

    Object.entries(mapping).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
}

function renderReportsChart(summary) {
    const canvas = document.getElementById("reports-chart");
    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    const chartData = [
        summary.risk_breakdown?.urgent || 0,
        summary.risk_breakdown?.stable || 0,
    ];

    if (reportsChart) {
        reportsChart.destroy();
    }

    reportsChart = new Chart(canvas, {
        type: "doughnut",
        data: {
            labels: ["Urgent", "Stable"],
            datasets: [
                {
                    data: chartData,
                    backgroundColor: ["#ef4444", "#00c4cc"],
                    borderWidth: 0,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        boxWidth: 10,
                        color: "#334155",
                        font: {
                            size: 11,
                            weight: "bold",
                        },
                    },
                },
            },
            cutout: "68%",
        },
    });
}

async function loadReportsSummary() {
    const status = document.getElementById("reports-status");
    try {
        const summary = await fetchJson("/reports/summary");
        updateReportCards(summary);
        renderReportsChart(summary);
        if (status) {
            status.textContent = "Live summary from SQLite";
        }
    } catch (error) {
        console.error("Reports Error:", error);
        if (status) {
            status.textContent = "Unable to load report summary";
            status.classList.add("text-red-500");
        }
    }
}

function setActiveNav(viewName) {
    document.querySelectorAll("[data-view-link]").forEach((link) => {
        const isActive = link.dataset.viewLink === viewName;
        link.classList.toggle("nav-link-active", isActive);
    });
}

function setActiveView(viewName) {
    const supportedViews = ["dashboard", "suppliers", "reports"];
    const normalizedView = supportedViews.includes(viewName) ? viewName : "dashboard";

    supportedViews.forEach((view) => {
        const section = document.getElementById(`view-${view}`);
        if (section) {
            section.classList.toggle("hidden", view !== normalizedView);
        }
    });

    setActiveNav(normalizedView);

    if (normalizedView === "dashboard") {
        loadInventoryFromDB();
    }
    if (normalizedView === "suppliers") {
        loadSuppliers();
    }
    if (normalizedView === "reports") {
        loadReportsSummary();
    }
}

function getViewFromHash() {
    const viewName = window.location.hash.replace("#", "");
    return viewName || "dashboard";
}

function navigateToView(viewName) {
    if (window.location.hash === `#${viewName}`) {
        setActiveView(viewName);
        return;
    }
    window.location.hash = viewName;
}

function switchTab(evt, tabId) {
    const contents = document.getElementsByClassName("tab-content");
    for (let index = 0; index < contents.length; index += 1) {
        contents[index].classList.remove("active");
    }

    const tabs = evt.currentTarget.parentNode.getElementsByTagName("button");
    for (let index = 0; index < tabs.length; index += 1) {
        tabs[index].classList.remove("tab-active");
    }

    document.getElementById(tabId).classList.add("active");
    evt.currentTarget.classList.add("tab-active");
}

function generatePO(sku) {
    alert(`[Automation] PO generated for ${sku}. Connecting to supplier...`);
}

function showMockAction(message) {
    const toast = document.getElementById("toast");
    if (!toast) {
        alert(message);
        return;
    }

    toast.textContent = message;
    toast.classList.remove("translate-y-20", "opacity-0");
    toast.classList.add("translate-y-0", "opacity-100");

    window.setTimeout(() => {
        toast.classList.add("translate-y-20", "opacity-0");
        toast.classList.remove("translate-y-0", "opacity-100");
    }, 2200);
}

function logout() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(NAME_KEY);
    window.location.href = "login.html";
}

function initializeNavigation() {
    document.querySelectorAll("[data-view-link]").forEach((link) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            navigateToView(link.dataset.viewLink);
        });
    });

    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {
        logoutButton.addEventListener("click", logout);
    }

    window.addEventListener("hashchange", () => {
        setActiveView(getViewFromHash());
    });

    setActiveView(getViewFromHash());
}

window.switchTab = switchTab;
window.generatePO = generatePO;
window.showMockAction = showMockAction;

document.addEventListener("DOMContentLoaded", () => {
    if (!requireLogin()) {
        return;
    }

    initializeNavigation();
});