import requests
from requests.auth import HTTPDigestAuth
from bs4 import BeautifulSoup
from enum import Enum
import os
from zeroconf import Zeroconf, ServiceBrowser
import socket
import json
import time

class BootMode(Enum):
    NORMAL = 0
    SAFE = 1


class Rio:

    REBOOT_ENDPOINT = '/rtexecsvc/RebootEx'
    BEGIN_ACTION_ENDPOINT = '/siws/BeginAction'
    SET_SYS_IMG_ENDPOINT = '/siws/SetSystemImage'
    PROGRESS_ENDPOINT = '/siws/Progress'
    FW_UPDATE_ENDPOINT = '/nisysapi/server_firmware'
    LOGIN_ENDPOINT = '/login'

    def __init__(self, ip: str, port: int = 80, username: str = 'admin', password: str = ''):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.session = requests.session()
        self.action_id = None
        self.directory = None
        self.file_name = None

    '''Reboots device into selected mode and returns True if reboot was succesful, False otherwise'''
    def reboot(self, mode: BootMode = BootMode.NORMAL):
        response = self.session.post(f'http://{self.ip}:{str(self.port)}{Rio.REBOOT_ENDPOINT}',
                                     files={}, data={'RebootIn': 0, 'BootMode': mode.value})
        return response.status_code == 202

    # ActionID format (X stands for capital letter, 0 for number): {00XX00X0-000X-XX00-X0X0-X000XXXX0000}
    '''Starts an action and returns the related new folder on the device'''
    def begin_action(self, action_id: str):
        response = self.session.post(f'http://{self.ip}:{str(self.port)}{Rio.BEGIN_ACTION_ENDPOINT}', files={},
                                     data={'ActionId': action_id, 'CustomLockHolder': '666'})
        xml = response.content.decode('utf-8')
        soup = BeautifulSoup(xml, 'xml')
        self.action_id = action_id
        self.directory = soup.findAll('BeginAction')[0].get('Directory')
        return self.directory

    '''Uploads file in the action directory'''
    def put_image_file(self, file_name: str):
        response = self.session.put(f'http://{self.ip}:{str(self.port)}/files{self.directory}/{file_name}',
                                    data=open(file_name, 'rb'),
                                    auth=HTTPDigestAuth(self.username, self.password))
        self.file_name = file_name

    '''Starts flashing uploaded image'''
    def set_system_image(self):
        if self.action_id is None or self.directory is None:
            raise Exception('No system image file uploaded yet.')

        response = self.session.post(f'http://{self.ip}:{str(self.port)}{Rio.SET_SYS_IMG_ENDPOINT}',
                                     data={'Blacklist': '', 'ActionID': self.action_id,
                                           'Timeout': '180000',
                                           'Options': '8204', 'LocalPath': f'{self.directory}/{self.file_name}'},
                                     files={})
        soup = BeautifulSoup(response.content.decode('utf-8'), 'xml')
        elements = soup.findAll('SetSystemImage')
        if elements is None or len(elements) == 0 or elements[0].get('Result') != '0':
            raise Exception('Error while setting system image.')

    '''Returns a string representing an XML with info on the flashing process status'''
    def get_deploy_progress(self):
        response = self.session.get(f'http://{self.ip}:{str(self.port)}{Rio.PROGRESS_ENDPOINT}')
        return response.content.decode('utf-8')

    def update_firmware(self, file_name: str):
        size: int = os.stat(file_name).st_size
        response = self.session.post(f'http://{self.ip}:{str(self.port)}{Rio.FW_UPDATE_ENDPOINT}',
                                     data={'Version': '00010001', 'Plugins': 'nisyscfg,crio', 'Items': 'system,system',
                                           'response_encoding': 'UTF-8', 'Function': 'BeginFirmwareChange',
                                           'StopTasks': '1', 'ImageLength': f'{size:02x}'.upper()})
        print(response.content)

    def login(self):
        response = self.session.post(f'http://{self.ip}:{self.port}{Rio.LOGIN_ENDPOINT}',
                                     auth=HTTPDigestAuth(self.username, self.password))
        print(response.status_code)


class Listener:

    def __init__(self, finder):
        self.finder = finder

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        ip: str = socket.inet_ntoa(info.address)
        if 'NI-cRIO' not in name:
            return
        if info.properties[b'DevClass'] != b'cRIO':
            return
        self.finder.on_new_rio({
            'IPAddress': ip,
            'ProdName': info.properties[b'ProdName'].decode('utf-8'),
            'SerialNo': info.properties[b'SerialNo'].decode('utf-8'),
            'MAC': info.properties[b'MAC'].decode('utf-8')
        })


class RioFinder:

    SERVICE_NAME = '_ni._tcp.local.'

    def __init__(self):
        self.zeroconf = Zeroconf()
        self.listener = Listener(self)
        self.browser = ServiceBrowser(self.zeroconf, RioFinder.SERVICE_NAME, self.listener)
        self.current_list = []

    def stop(self):
        self.browser.cancel()

    def on_new_rio(self, rio: dict):
        if json.dumps(rio, sort_keys=True) not in self.current_list:
            self.current_list.append(rio)


if __name__ == "__main__":
    # Example usage
    finder = RioFinder()
    time.sleep(5)
    finder.stop()
    if len(finder.current_list) == 0:
        print('No devices found.')
        exit(1)
    rio = Rio(finder.current_list[0]['IPAddress'])
    result = rio.reboot(BootMode.NORMAL)
    #directory = rio.begin_action('{02CF21F5-820E-FF87-A8D9-A504FCFE9558}')
    #rio.put_file('systemimage.tar.gz')
    #rio.set_system_image()
    #print(rio.get_progress())
    #rio.login()
    #rio.update_firmware('process.txt')
