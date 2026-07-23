frappe.pages['lunch-kiosk'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Lunch Kiosk',
        single_column: true
    });
    new LunchKiosk(page);
}

class LunchKiosk {
    constructor(page) {
        this.wrapper = $(page.body);
        this.make();
    }
    make() {
        this.wrapper.html(`<div class="lunch-kiosk-grid" style="display:flex;flex-wrap:wrap;gap:12px;padding:16px;"></div>`);
        this.grid = this.wrapper.find('.lunch-kiosk-grid');
        this.load();
    }
    load() {
        frappe.call({
            method: 'hr_custom.hr_custom.api.get_kiosk_data',
            callback: (r) => this.render(r.message)
        });
    }
    render(data) {
        this.grid.empty();
        data.forEach(emp => {
            let tile = $(`
                <div class="lunch-tile" style="width:140px;height:100px;border-radius:8px;
                    display:flex;align-items:center;justify-content:center;text-align:center;
                    font-weight:600;cursor:pointer;padding:8px;
                    background:${emp.ticked ? '#4caf50' : '#eee'};
                    color:${emp.ticked ? '#fff' : '#333'};">
                    ${emp.employee_name}
                </div>`);
            tile.on('click', () => this.toggle(emp.name, tile));
            this.grid.append(tile);
        });
    }
    toggle(employee, tile) {
        frappe.call({
            method: 'hr_custom.hr_custom.api.toggle_lunch',
            args: { employee },
            callback: (r) => {
                let ticked = r.message.ticked;
                tile.css({ background: ticked ? '#4caf50' : '#eee', color: ticked ? '#fff' : '#333' });
            }
        });
    }
}
