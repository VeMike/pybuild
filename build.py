from pymsbuild import *
import logging


def prebuild(user_defined_config):
    log = logging.getLogger(__name__)
    # Do some fancy prebuild stuff
    log.info('Performing prebuild operations...')

    # ... some operations

    # ... access config
    my_conf = user_defined_config['my_fancy_object']

    # ..further operations

    # Return True to indicate success
    return True


def postbuild(user_defined_config):
    log = logging.getLogger(__name__)
    # Do some fancy postbuild stuff
    log.info('Performing postbuild operations...')

    # ... some operations

    # ... access config
    my_conf = user_defined_config['my_fancy_object']

    # ..further operations

    # Return True to indicate success
    return True


# Use the configurator to read configuration json. Default path is: './build.config.json'
config = Configurator()
# Create an instance of the MsBuilder (pre- and postbuild are optional)
builder = MsBuilder(config, prebuild=prebuild, postbuild=postbuild)
# Build the project/solution as defined in the configuration
builder.build()



