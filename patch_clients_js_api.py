import re

with open('planner_service/static/js/clients.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix trash empty call
content = content.replace(
    "await API.request('/api/clients/trash/empty', 'DELETE');",
    "await API.request('DELETE', '/clients/trash/empty');"
)

# Fix delete call
content = content.replace(
    "await API.request('/api/clients/' + this.editingClientId, 'DELETE');",
    "await API.request('DELETE', '/clients/' + this.editingClientId);"
)

# Fix restore call
content = content.replace(
    "await API.request('/api/clients/' + clientId + '/restore', 'POST');",
    "await API.request('POST', '/clients/' + clientId + '/restore');"
)

# Fix load call
content = content.replace(
    "const endpoint = this.isTrashMode ? '/api/clients?deleted=true' : '/api/clients';",
    "const endpoint = this.isTrashMode ? '/clients?deleted=true' : '/clients';"
)
content = content.replace(
    "const data = await API.request(endpoint);",
    "const data = await API.request('GET', endpoint);"
)

with open('planner_service/static/js/clients.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("clients.js fixes applied!")
