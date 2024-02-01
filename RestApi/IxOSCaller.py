"""
An interface to IxOS REST APIs that allows you to connect to a IxOS chassis.
This is intended for Linux based chassis including IxVM chassis, but also
works with limited functionality for Windows chassis.
"""

import sys
import os
import json
import time
import requests
import paramiko
import time

# handle urllib3 differences between python versions
if sys.version_info[0] == 2 and ((sys.version_info[1] == 7 and sys.version_info[2] < 9) or sys.version_info[1] < 7):
    import requests.packages.urllib3
else:
    import urllib3

class IxRestException(Exception):
    pass

class IxRestSession(object):
    """
    class for handling HTTP requests/response for IxOS REST APIs
    Constructor arguments:
    chassis_address:    addrress of the chassis
    Optional arguments:
        api_key:        API key or you can use authenticate method \
                        later to get it by providing user/pass.
        verbose:        If True, will print every HTTP request or \
                        response header and body.
        timeout:        Time to wait (in seconds) while polling \
                        for async operation.
        poll_interval:  Polling inteval in seconds.
    """

    def __init__(self, chassis_address, username=None, password=None, api_key=None,timeout=600, poll_interval=2, verbose=False, insecure_request_warning=False):

        self.chassis_ip = chassis_address
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.verbose = verbose
        self._authUri = '/platform/api/v1/auth/session'
        self.username = username
        self.password = password

        # ignore self sign certificate warning(s) if insecure_request_warning=False
        if not insecure_request_warning:
            try:
                if sys.version_info[0] == 2 and ((sys.version_info[1] == 7 and sys.version_info[2] < 9) or sys.version_info[1] < 7):
                    requests.packages.urllib3.disable_warnings()
                else:
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except AttributeError:
                print('WARING:You are using an old urllib3 version which does not support handling the certificate validation warnings. Please upgrade urllib3 using: pip install urllib3 --upgrade')

    # try to authenticate with default user/password if no api_key was provided
        if not api_key:
            self.authenticate(username=self.username, password=self.password)

    def get_ixos_uri(self):
        return 'https://%s/chassis/api/v2/ixos' % self.chassis_ip

    def get_headers(self):
        # headers should at least contain these two
        return {
            "Content-Type": "application/json",
            'x-api-key': self.api_key
        }

    def authenticate(self, username="admin", password="admin"):
        """
        we need to obtain API key to be able to perform any REST
        calls on IxOS
        """
        payload = {
            'username': username,
            'password': password,
            'rememberMe': False,
            'resetWeakPassword': False
        }
        response = self.http_request(
            'POST',
            'https://{address}{uri}'.format(address=self.chassis_ip,
                                            uri=self._authUri),
            payload=payload
        )
        self.api_key = response.data['apiKey']

    def http_request(self, method, uri, payload=None, params=None):
        """
        wrapper over requests.requests to pretty-print debug info
        and invoke async operation polling depending on HTTP status code (e.g. 202)
        """
        try:
            # lines with 'debug_string' can be removed without affecting the code
            if not uri.startswith('http'):
                uri = self.get_ixos_uri() + uri

            if payload is not None:
                payload = json.dumps(payload, indent=2, sort_keys=True)

            headers = self.get_headers()
            response = requests.request(
                method, uri, data=payload, params=params,
                headers=headers, verify=False, timeout=10
            )

            # debug_string = 'Response => Status %d\n' % response.status_code
            data = None
            try:
                data = response.content.decode()
                data = json.loads(data) if data else None
            except:
                print('Invalid/Non-JSON payload received: %s' % data)
                data = None

            if str(response.status_code)[0] == '4':
                raise IxRestException("{code} {reason}: {data}.{extraInfo}".format(
                    code=response.status_code,
                    reason=response.reason,
                    data=data,
                    extraInfo="{sep}{msg}".format(
                        sep=os.linesep,
                        msg="Please check that your API key is correct or call IxRestSession.authenticate(username, password) in order to obtain a new API key."
                    ) if str(response.status_code) == '401' and uri[-len(self._authUri):] != self._authUri else ''
                )
                )

            if response.status_code == 202:
                result_url = self.wait_for_async_operation(data)
                return result_url
            else:
                response.data = data
                return response
        except:
            raise

    def wait_for_async_operation(self, response_body):
        """
        method for handeling intermediate async operation results
        """
        try:
            print('Polling for async operation ...')
            operation_status = response_body['state']
            start_time = int(time.time())
            while operation_status == 'IN_PROGRESS':
                response = self.http_request('GET', response_body['url'])
                response_body = response.data
                operation_status = response_body['state']
                if int(time.time() - start_time) > self.timeout:
                    raise IxRestException(
                        'timeout occured while polling for async operation')

                time.sleep(self.poll_interval)

            if operation_status == 'SUCCESS':
                return response.data['resultUrl']
            elif operation_status == 'COMPLETED':
                return response.data['resultUrl']
            elif operation_status == 'ERROR':
                return response.data['message']
            else:
                raise IxRestException("async failed")
        except:
            raise
        finally:
            print('Completed async operation')
    

    def get_license_servers(self):
        url = f'https://{self.chassis_ip}/platform/api/v2/licensing/servers'
        return self.http_request('GET', url, params="").data

    def check_internet_connectivity(self, id):
        url = f'https://{self.chassis_ip}/platform/api/v2/licensing/servers/{id}/operations/testbackendconnectivity'
        resultUrl = self.http_request('POST', url, params="")
        if "http" in resultUrl:
            return (self.http_request('GET', resultUrl, params=" ").json())

    
    def set_new_license_server(self, server_ip):
        url = f'https://{self.chassis_ip}/platform/api/v2/licensing/servers'
        params = {
        "host": server_ip,
        "isActive": True
        }
        return self.http_request('POST', url, payload=params).data

    def unset_new_license_server(self, id):
        url = f'https://{self.chassis_ip}/platform/api/v2/licensing/servers/{id}'
        return self.http_request('DELETE', url, payload="").data

   
    def do_license_check_operation(self,operation="get"):
        data = {}
        # Create an instance of the SSH client
        ssh = paramiko.SSHClient()

        # Automatically add the server's SSH key (for the first time only)
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the server
        ssh.connect(self.chassis_ip, username=self.username, password=self.password)
        chan = ssh.invoke_shell(width=500)

        # Ssh and wait for the password prompt.
        self.send_command_and_print_info(chan, 'enter chassis\n')

        if operation.lower() == "get":
            license_check = self.send_command_and_print_info(chan, 'show license-check\n')
            return license_check[0].split("\r\n")[1].replace('\x1b[39m', '').replace('\x1b[33m', '')
            
        if operation.lower() in ["enable", "disable" ]:
            license_check = self.send_command_and_print_info(chan, f'set license-check {operation.lower()}\n')
            return license_check[0].split("\r\n")[1].replace('\x1b[39m', '').replace('\x1b[33m', '')

        # Close the connection
        ssh.close()
        return data


    def send_command_and_print_info(self, chan, command):
        chan.send(command)
        time.sleep(5)
        resp = ''
        rs = []
        while not resp.endswith('# '):
            resp = chan.recv(9999)
            resp = str(resp, 'UTF-8')
            if "enter chassis" not in command:
                rs.append(resp)
        return rs
    
    def get_activation_code_info(self, id, activationCode):
        url =  f"https://{self.chassis_ip}/platform/api/v2/licensing/servers/{id}/operations/retrieveactivationcodeinfo"
        payload = {'activationCode': activationCode}
        resultUrl =  self.http_request('POST', url, payload=payload)
        if "http" in resultUrl:
            return(self.http_request('GET', resultUrl, params=" ").json())

    def activate_licenses(self, id, list_of_activation_code_quantity):
        url =  f"https://{self.chassis_ip}/platform/api/v2/licensing/servers/{id}/operations/activate"
        resultUrl =  self.http_request('POST', url, payload=list_of_activation_code_quantity)
        if "http" in resultUrl:
            res = self.http_request('GET', resultUrl, params=" ").json()
            if len(list(res.keys())) == 1 and list(res.keys())[0] == "href":
               return self.http_request('GET', resultUrl, params=" ").json().get("href")
            return self.http_request('GET', resultUrl, params=" ").json().get("message")

    def deactivate_licenses(self, id, list_of_activation_code_quantity):
        url =  f"https://{self.chassis_ip}/platform/api/v2/licensing/servers/{id}/operations/deactivate"
        resultUrl =  self.http_request('POST', url, payload=list_of_activation_code_quantity)
        if "http" in resultUrl:
            return self.http_request('GET', resultUrl, params=" ").json().get("href")

    def get_licenses(self, id=None, params=None):
        url = f'https://{self.chassis_ip}/platform/api/v2/licensing/servers/{id}/operations/retrievelicenses'
        url = self.http_request('POST', url, params=params)
        if str(url) != '<Response [200]>':
            #print('Linux Chassis')
            return self.http_request('GET', url, params=params)
        else:
            #print('Windows Chassis')
            id_url = f'https://{self.chassis_ip}/platform/api/v2/licensing/servers/1/operations/retrievelicenses/1/result'
            return self.http_request('GET', id_url, params=params)

    

if __name__ == '__main__':
    pass
