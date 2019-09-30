import requests
from requests.auth import HTTPDigestAuth
from bs4 import BeautifulSoup
from enum import Enum


class BootMode(Enum):
    NORMAL = 0
    SAFE = 1


class Rio:

    REBOOT_ENDPOINT = '/rtexecsvc/RebootEx'
    BEGIN_ACTION_ENDPOINT = '/siws/BeginAction'
    SET_SYS_IMG_ENDPOINT = '/siws/SetSystemImage'
    PROGRESS_ENDPOINT = '/siws/GetProgress'

    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.session = requests.session()
        self.action_id = None
        self.directory = None
        self.file_name = None

    def reboot(self, mode: BootMode = BootMode.NORMAL):
        response = self.session.post(f'http://{self.ip}:{str(self.port)}{Rio.REBOOT_ENDPOINT}',
                                     files={}, data={'RebootIn': 0, 'BootMode': mode.value})
        return response.status_code == 202

    def begin_action(self, action_id: str):
        response = self.session.post(f'http://{self.ip}:{str(self.port)}{Rio.BEGIN_ACTION_ENDPOINT}', files={},
                                     data={'ActionId': action_id, 'CustomLockHolder': '666'})
        xml = response.content.decode('utf-8')
        soup = BeautifulSoup(xml, 'xml')
        self.action_id = action_id
        self.directory = soup.findAll('BeginAction')[0].get('Directory')
        return self.directory

    def put_file(self, file_name: str):
        response = self.session.put(f'http://{self.ip}:{str(self.port)}/files{self.directory}/{file_name}',
                                    data=open(file_name, 'rb'),
                                    auth=HTTPDigestAuth('admin', ''))
        self.file_name = file_name

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

    def get_progress(self):
        response = self.session.get(f'http://{self.ip}:{str(self.port)}{Rio.PROGRESS_ENDPOINT}')


if __name__ == "__main__":
    # Example usage
    rio = Rio('172.16.3.7', 80)
    result = rio.reboot(1)
    directory = rio.begin_action('{02CF21F5-820E-FF87-A8D9-A504FCFE9558}')
    rio.put_file('systemimage.tar.gz')
    rio.set_system_image()
    rio.get_progress()
