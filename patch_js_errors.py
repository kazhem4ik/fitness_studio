import re

with open('planner_service/static/js/appointments.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_catch = """        } catch (err) {
            // Если ошибка пришла от сервера, она может быть объектом
            if (err.detail) {
                alert('Ошибка: ' + err.detail);
            } else {
                showToast('❌ ' + err.message);
            }
        }"""

new_catch = """        } catch (err) {
            if (err.message && err.message.includes('находится в корзине')) {
                alert(err.message);
            } else {
                showToast('❌ ' + err.message);
            }
        }"""

content = content.replace(old_catch, new_catch)

with open('planner_service/static/js/appointments.js', 'w', encoding='utf-8') as f:
    f.write(content)

with open('planner_service/static/js/clients.js', 'r', encoding='utf-8') as f:
    content_clients = f.read()

old_catch_clients = """        } catch (e) {
            alert("Ошибка сохранения клиента");
        }"""

new_catch_clients = """        } catch (e) {
            if (e.message) {
                alert(e.message);
            } else {
                alert("Ошибка сохранения клиента");
            }
        }"""
        
content_clients = content_clients.replace(old_catch_clients, new_catch_clients)

with open('planner_service/static/js/clients.js', 'w', encoding='utf-8') as f:
    f.write(content_clients)

print("JS error handling patched!")
