# install custom_components from https://api.github.com/repos/AlexxIT/SonoffLAN/releases/latest if not existing

import os

async def install_components():
    '''
    Download custom_components from latest release at https://github.com/AlexxIT/SonoffLAN
    '''
    from io import BytesIO
    import shutil, sys
    from zipfile import ZipFile
    from aiohttp import ClientSession, ClientTimeout
    print('Attempting to install custom_components')
    async with ClientSession(timeout=ClientTimeout(total=5.0)) as session:
        async with session.get('https://api.github.com/repos/AlexxIT/SonoffLAN/releases/latest') as resp:
            if resp.status == 200:
                data = await resp.json()
                zipfile_url = data.get('zipball_url', None)
                if zipfile_url:
                    print('retrieving: {}'.format(zipfile_url))
                    async with session.get(zipfile_url) as r:
                        if r.status == 200:
                            SonoffLAN = ZipFile(BytesIO(await r.read()))
                            name_list = SonoffLAN.namelist()
                            root = name_list[0]
                            files = [name for name in name_list if 'custom_components' in name]
                            print('Extracting: {}'.format('\n'.join(files)))
                            SonoffLAN.extractall(members = files)
                            shutil.move(root+'custom_components', './')
                            if len(root) > 3:
                                shutil.rmtree(root)
                            print('Installed custom_components')
                            return True
            print('Could not install custom_components from https://api.github.com/repos/AlexxIT/SonoffLAN')
            sys.exit(1)
                
def check_setup():
    if not os.path.exists('./custom_components'):
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(install_components())
                
if __name__ == "__main__":
    check_setup()
    