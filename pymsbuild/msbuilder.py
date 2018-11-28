import logging.config
import json
from subprocess import run, CalledProcessError
from os.path import isfile, join, dirname, expandvars
from os import walk
from re import search


class MsBuilder:

    def __init__(self, configurator, prebuild=None, postbuild=None):
        # Get a logger
        self._log = logging.getLogger(__name__ + ".{0}".format(self.__class__.__name__))
        # Assign the prebuild callback
        self._prebuild = prebuild
        # Assign the postbuild callback
        self._postbuild = postbuild
        # Access the configuration dictionary
        self._build_config = configurator.configuration

    def build(self):
        # Check, if the build configuration was read
        if self._build_config is None:
            self._log.error('Build cannot be performed, since the build configuration is not available')

        # Call the prebuild operations
        if not self._call(self._prebuild, 'prebuild'):
            return

        # Do the actual build
        if not self._run():
            self._log.fatal('The build failed.')
            return

        # Call the postbuild operations
        if not self._call(self._postbuild, 'postbuild'):
            return

    def _run(self):
        self._log.info('Starting to build')
        # Nuget dependencies need to be fetched before the build
        nuget_cmd = _NugetCmd(self._build_config['solution']['path'], self._build_config['build_tools']['nuget'])
        # Fetch the dependancies, if there are any
        if not nuget_cmd.fetch_dependencies():
            return False
        # Create a new instance of the MsBuildCmd
        build_cmd = _MsBuildCmd(self._build_config['build_tools']['msbuild'])
        # Iterate the projects
        for project in self._build_config['solution']['projects']:
            # Use the msbuild cmd to build the project
            if not build_cmd.build_project(project['project']):
                self._log.fatal('Build of project "{0}" failed. Aborting build'.format(project['project']['name']))
                return False
        self._log.info('Build was successful')
        return True

    def _call(self, callback, callback_kind):
        # Check, if we need to invoke
        if callback is None:
            # Log, that the callback was empty
            self._log.info('No {0} operations were set'.format(callback_kind))
            # The callback always succeeds, if there is none
            return True
        self._log.info('{0} operations will be performed now'.format(callback_kind))
        # Call the callback
        if not callback(self._build_config['user_defined_config']):
            self._log.fatal('The operation "{0}" failed'.format(callback_kind))
            # Return false, since operation failed
            return False
        self._log.debug('{0} operations were successful'.format(callback_kind))
        return True


class Configurator:

    def __init__(self, build_config='./build.config.json'):
        # Read the configuration file
        self._config = Configurator._read_configuration(build_config)
        # Configure python logging
        if self._config is not None and 'logging' in self._config:
            # Configure logging
            logging.config.dictConfig(self._config['logging'])
        else:
            # Just do a basic configuration
            logging.basicConfig(level=logging.INFO)

    @property
    def configuration(self):
        return self._config

    @staticmethod
    def _read_configuration(build_config):
        # Check, if the logging configuration exists
        if not isfile(build_config):
            return None
        # Open the configuration file and load it
        with open(build_config) as file:
            # Load the file as dictionary
            config = json.load(file)
        # Return the loaded dictionary
        return config


class _MsBuildCmd:
    # The AssemblyInfo.cs for versioning
    _ASSEMBLYINFO = 'AssemblyInfo.cs'
    # The name of msbuild
    _MS_BUILD_NAME = 'MSBuild.exe'
    # The build target command line switch for msbuild
    _BUILD_TARGET = '/target:Build'
    # The property command line switch for msbuild
    _BUILD_PROPERTY = '/property:'

    def __init__(self, msbuild):
        self._log = logging.getLogger(__name__ + ".{0}".format(self.__class__.__name__))
        # The dictionary, that holds some basic msbuild configuration
        self._msbuild = msbuild
        # The path to the exe of msbuild
        self._msbuild_path = None
        # Recursively search for msbuild
        self._find_msbuild()

    def build_project(self, project):
        # Is MSBuild.exe available?
        if self._msbuild_path is None:
            # Fatal, since we can not build
            self._log.fatal('MSBuild.exe was not found in any of the defined paths')
            # Return false to indicate an error
            return False
        # Check, if we need to update the AssemblyVersion
        if 'versioning' in project:
            self._log.info('A configuration for versioning was found. Version will be updated')
            # Use the finder, to search for AssemblyInfo.cs
            finder = _FileFinder([dirname(project['path'])])
            # The path to AssemblyInfo.cs
            assembly_info = finder.find_file(_MsBuildCmd._ASSEMBLYINFO)
            # Check, if the file was found
            if assembly_info is not None:
                # Create a new versioner
                versioner = _Versioner(assembly_info, project['versioning'])
                # Update the verison
                versioner.increment()
            else:
                self._log.warning('AssemblyInfo.cs was not found. Version will not be updated during build')
        # Build the project using msbuild
        if not self._call_msbuild(project):
            return False
        return True

    def _call_msbuild(self, project):
        # Access the projects path
        project_path = project['path']
        # Log the current build
        self._log.info('Currently building project "{0}" at "{1}"'.format(project['name'], project_path))
        # Check, if the project file exists
        if not isfile(project_path):
            self._log.fatal('Could not find project at "{0}"'.format(project_path))
            return False
        # Join the defined build properties
        properties = self._join_build_properties(project['build_properties'])
        # Create the command list
        commands = [self._msbuild_path, project_path, _MsBuildCmd._BUILD_TARGET, properties]
        # Use the subprocess module to call msbuild via command line
        result = run(commands)
        # Check the return code
        try:
            # Will raise an exception, if the return code is != 0
            result.check_returncode()
        except CalledProcessError as e:
            # Log the error
            self._log.error('The return code of the command "{0}" was non zero: {1}. Stdout: {2}, Stderr: {3}'
                            .format(e.args, e.returncode, e.stdout, e.stderr))
            return False
        # If reached, the build succeeded
        self._log.info('The command "{0}" for the projected build succeeded. Stdout: {1}, Stderr {2}'
                       .format(result.args, result.stdout, result.stderr))
        # Indicate success
        return True

    def _join_build_properties(self, build_properties):
        # Log
        self._log.debug('Joining build properties for command line')
        # Join the build properties
        property_list = ';'.join(['{0}={1}'.format(key, value) for key, value in build_properties.items()])
        # Log
        self._log.debug('Joined properties: {0}'.format(property_list))
        # Return the list
        return _MsBuildCmd._BUILD_PROPERTY + property_list

    def _find_msbuild(self):
        # Look for msbuild in the specified paths
        finder = _FileFinder(self._msbuild['paths'])
        # Find the file
        self._msbuild_path = finder.find_file(_MsBuildCmd._MS_BUILD_NAME)


class _NugetCmd:
    # The name of the nuget executable
    _NUGET_EXE = 'nuget.exe'
    # The nuget option passed to the exe
    _NUGET_OPTION = 'restore'
    # The name of the file, that defines nuget dependencies
    _PACKAGES_CONFIG = 'packages.config'

    def __init__(self, solution_path=None, nuget=None):
        # Initialize the logger
        self._log = logging.getLogger(__name__ + ".{0}".format(self.__class__.__name__))
        # The path to the .sln file
        self._solution_path = solution_path
        # The nuget object
        self._nuget = nuget

    def fetch_dependencies(self):
        self._log.info('Checking, if the solution uses nuget')
        # Check, if the solution uses nuget
        if self._uses_nuget():
            return self._call_nuget()
        # Operation always succeeds, if there are no dependencies
        return True

    def _call_nuget(self):
        # Log
        self._log.info("Fetching nuget dependencies")
        # Find nuget in the specified paths
        if self._nuget is None or 'paths' not in self._nuget:
            self._log.error('Nuget is required, but the path to it was not specified')
            # The build fails now
            return False
        # Find nuget
        finder = _FileFinder(self._nuget['paths'])
        nuget_path = finder.find_file(_NugetCmd._NUGET_EXE)
        # Check, if the path was found
        if nuget_path is None:
            self._log.error("Nuget was not found in any of the paths. The build will fail")
            # The build fails
            return False
        # Use the subprocess module to call nuget.exe via command line
        result = run([nuget_path, _NugetCmd._NUGET_OPTION, self._solution_path])
        # Check the return code
        try:
            # Will raise an exception, if the return code is != 0
            result.check_returncode()
        except CalledProcessError as e:
            # Log the error
            self._log.error('The return code of the command "{0}" was non zero: {1}. Stdout: {2}, Stderr: {3}'
                            .format(e.args, e.returncode, e.stdout, e.stderr))
            return False
        # Everything went fine
        return True

    def _uses_nuget(self):
        # Check, if the solution file exists
        if not isfile(self._solution_path):
            # log
            self._log.error('The solution file {0} does not exist'.format(self._solution_path))
            return False
        self._log.debug('Checking if {0} uses nuget'.format(self._solution_path))
        # Get the directory of the solution
        solution_dir = dirname(self._solution_path)
        # Search the solution directory for any 'packages.config'. If one is found, assume that nuget is used.
        finder = _FileFinder([solution_dir])
        # Find packages.config
        path = finder.find_file(_NugetCmd._PACKAGES_CONFIG)
        # Check, if the file was found
        if path is None:
            # Log
            self._log.info('The solution {0} does not use nuget (no {1} was found).'.format(self._solution_path,
                                                                                            _NugetCmd._NUGET_OPTION))
            return False
        # If the file is found, assume that the solution uses nuget
        self._log.info('{0} found: {1}!. Nuget.exe will be called to fetch libraries'.format(_NugetCmd._PACKAGES_CONFIG,
                                                                                             path))
        return True


class _Versioner:
    # The format string for the assembly version
    _ASSEMBLY_VERSION_FORMAT = '[assembly: AssemblyVersion(\"{0}\")]\n'
    # The format string for the assembly file version
    _ASSEMBLY_FILE_VERSION_FORMAT = '[assembly: AssemblyFileVersion(\"{0}\")]\n'
    # The assembly version attribute in AssemblyInfo.cs
    _ASSEMBLY_VERSION_PATTERN = r'\[assembly: AssemblyVersion\("(.\..\..\..)"\)\]'
    # The assembly file version pattern in AssemblyInfo.cs
    _ASSEMBLY_FILE_VERSION_PATTERN = r'\[assembly: AssemblyFileVersion\("(.\..\..\..)"\)\]'

    def __init__(self, file_path, versioning):
        self._log = logging.getLogger(__name__ + ".{0}".format(self.__class__.__name__))
        # The path to the file (AssemblyInfo.cs)
        self._file_path = file_path
        # Split the string into its version sections
        self._version_parts = versioning.split('.')
        # A list containing the files contents
        self._file_content = []

    def increment(self):
        # Is there any need to change the version?
        if not any(symbol == '+' for symbol in self._version_parts):
            self._log.info('No AssemblyVersion update will be done, since the placeholder "+" was not specified')
            return
        # Open the file and read its contents
        with open(self._file_path, 'r') as file:
            # Read the full file
            self._file_content = file.readlines()
        # Iterate the contents of the file
        for index, line in enumerate(self._file_content):
            # Search for the pattern in the line
            match = search(_Versioner._ASSEMBLY_VERSION_PATTERN, line)
            # Do we have a match?
            if match is not None:
                incremented = self._increase_version(match.group(1))
                self._file_content[index] = _Versioner._ASSEMBLY_VERSION_FORMAT.format(incremented)
            # Search for the next pattern in the line
            match = search(_Versioner._ASSEMBLY_FILE_VERSION_PATTERN, line)
            # Do we have a match?
            if match is not None:
                incremented = self._increase_version(match.group(1))
                self._file_content[index] = _Versioner._ASSEMBLY_FILE_VERSION_FORMAT.format(incremented)
        # Write the contents of the file back
        with open(self._file_path, 'w') as file:
            file.writelines(self._file_content)

    def _increase_version(self, old_version):
        self._log.info('The version before the build is: {0}'.format(old_version))
        # Split the version string
        parts = old_version.split('.')
        # Iterate the versioning configuration
        for index, element in enumerate(self._version_parts):
            if element is not '+':
                continue
            # Update the version part
            new_version = int(parts[index]) + 1
            parts[index] = str(new_version)
        # Create the new version string
        version_string = '.'.join(parts)
        # Log
        self._log.info('The new version string is: {0}'.format(version_string))
        # Return the string
        return version_string


class _FileFinder:

    def __init__(self, paths):
        self._log = logging.getLogger(__name__ + ".{0}".format(self.__class__.__name__))
        # The list of paths, wherein files will be searched. Expand environment variables
        self._paths = [expandvars(path) for path in paths]

    def find_file(self, find_file):
        # Is it possible to directly define the path to a file in the file. Filter for those
        files = [path for path in self._paths if isfile(path)]
        # Is there any direct exe path?
        if len(files) >= 1:
            # Just take the first one
            file_path = files[0]
            # Log the used path
            self._log.info('Path used for msbuild: {0}'.format(file_path))
            # Return the path
            return file_path
        # No direct path was found. We need to walk each defined path
        for path in self._paths:
            # Log the currently search tree
            self._log.debug('Searching recursively for {0} in {1}'.format(find_file, path))
            # Walk the path recursively
            for root, dirs, files in walk(path):
                self._log.debug('Currently walking: {0}'.format(root))
                # Iterate through the current files in root and look for the passed file
                for file in files:
                    if file.lower() == find_file.lower():
                        # Join the path to the file
                        file_path = join(root, file)
                        # Log the used path
                        self._log.info('The file was found in: {0}'.format(file_path))
                        # Return the path
                        return file_path
        # The file was not found, return none
        self._log.info('The file {0} was not found in any of the paths'.format(find_file))
        return None
