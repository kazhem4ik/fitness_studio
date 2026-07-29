import re

with open('planner_service/static/js/clients.js', 'r', encoding='utf-8') as f:
    content = f.read()

# find the place in showClientDetails after cd-btn-close
old_close = """            document.getElementById('cd-btn-close').onclick = () => {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
            };"""

new_close = """            document.getElementById('cd-btn-close').onclick = () => {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
            };
            
            const btnDelete = document.getElementById('cd-btn-delete');
            if (btnDelete) {
                const newBtnDelete = btnDelete.cloneNode(true);
                btnDelete.parentNode.replaceChild(newBtnDelete, btnDelete);
                
                newBtnDelete.addEventListener('click', async () => {
                    if (confirm('Вы уверены? Клиент и все его данные отправятся в корзину.')) {
                        try {
                            await API.request('DELETE', '/clients/' + clientId);
                            document.getElementById('cd-btn-close').click();
                            this.loadClients();
                            if (window.showToast) window.showToast('Клиент удален в корзину');
                        } catch (e) {
                            alert('Ошибка удаления клиента');
                        }
                    }
                });
            }"""

content = content.replace(old_close, new_close)

with open('planner_service/static/js/clients.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("clients.js patched with cd-btn-delete!")
