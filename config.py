import yaml
import keyring
CONFIG_FILE = 'config.yaml'

with open(CONFIG_FILE, 'r') as f:
    try:
        settings = yaml.load(f)
        f.seek(0) #return to top of file to load again
        new_settings = yaml.load(f)
        ############################################################
        #This section will look for any passwords in the yaml file #
        #If a password is not set to 'Stored In Keyring' it will   #
        #store the file in the keyring and recreate the yaml       #
        #marking it as stored.  If it is 'Stored In Keyring'       #
        #it will retrieve it from the keyring                      #
        ############################################################
        for section in settings:
            #looks to see if config contains any passwords
            if 'password' in (settings[section]):
                password = settings[section]['password']
                #If it is already stored, it retrieves it and sets it into the variable class
                if password == 'Stored In Keyring':
                    application = section
                    username = settings[section]['username']
                    stored_pw = keyring.get_password(application, username)
                    settings[section]['password'] = stored_pw
                # If not, it stores the password in the keychain and preps the settings to rewrite
                else:
                    application = section
                    username = settings[section]['username']
                    keyring.set_password(application, username, password)
                    new_settings[section]['password'] = 'Stored In Keyring'

        f.close()
        # looks to see if new_settings was updated to remove any passwords and rewrite the settings file
        if settings != new_settings:
            new_f = open(CONFIG_FILE, 'w')
            new_f.write(yaml.dump(new_settings, default_flow_style=False))
            new_f.close()

    except yaml.YAMLError as exc:
        print('Cannot load config.yaml')

