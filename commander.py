
from RestApi.IxOSCaller import IxRestSession
from tabulate import tabulate

"""
set license-server <serverAddress>
unset license-server
show license-server
set license-check <enable/disable>
show license-check
show licenses
activation
deactivation

 """


session = IxRestSession("10.36.237.139", "admin", "xxx")

def get_licenses(id=1, session=None):
    #host_id = session.get_license_server_host_id(id=id)
    license_info = session.get_licenses(id=id).json()
    license_info_list= []
    headers = ["partNumber","activationCode", "quantity", "description", "maintenanceDate","expiryDate", "isExpired"]
    for item in license_info:
        license_info_list.append([  item["partNumber"],
                                    item["activationCode"], 
                                    item["quantity"], 
                                    item["description"].replace(",","_"),
                                    item["maintenanceDate"], 
                                    item["expiryDate"],
                                    str(item.get("isExpired", "NA"))])
    
    return tabulate(license_info_list, headers=headers, tablefmt='grid')


print(" \n\n========================================================= ")
print(session.get_license_servers())
print(" \n\n========================================================= ")
print(get_licenses(id=1, session=session))
print(" \n\n========================================================= ")
print(session.set_new_license_server(server_ip = "192.168.10.1"))
print(" \n\n========================================================= ")
print(session.do_license_check_operation(operation="get"))
print(" \n\n========================================================= ")
print(session.do_license_check_operation(operation="enable"))
print(" \n\n========================================================= ")
print(session.do_license_check_operation(operation="disable"))
print(" \n\n========================================================= ")
print(session.check_internet_connectivity(id=1))
print(" \n\n========================================================= ")
list_of_deactivation_code_quantity = [{'activationCode': "D3AA-E129-CBB2-34BB", "quantity": 1}]
print(session.deactivate_licenses(id=1, list_of_activation_code_quantity=list_of_deactivation_code_quantity))

print(get_licenses(id=1, session=session))
print(" \n\n========================================================= ")
list_of_activation_code_quantity = []
activationCodes = ["D3AA-E129-CBB2-34BB"]
for activationCode in activationCodes:
    out = session.get_activation_code_info(id=1, activationCode=activationCode)
    list_of_activation_code_quantity.append({'activationCode': out['activationCode'], "quantity": out['availableQuantity']})
#     # {'activationCode': 'D3AA-E129-CBB2-34BB', 'totalQuantity': 2, 'availableQuantity': 0, 'product': 'IxNetwork VE', 'description': 'IxNetwork VE'}

print(list_of_activation_code_quantity)
print(session.activate_licenses(id=1, list_of_activation_code_quantity=list_of_activation_code_quantity))
print(get_licenses(id=1, session=session))
print(" \n\n========================================================= ")
print(session.unset_new_license_server(id=3))
print(" \n\n========================================================= ")
print(session.get_license_servers())