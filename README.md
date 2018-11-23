# pybuild
A simple and configurable python script to build apps using MSBuild.

## Configuration
The script can be configured using a json file. An example of such a configuration file can be found in `build.config.json`

### Commented configuration example

Next up, a commented example of a configuration file

    {
        // Currently not in use. Can be left out
        "json_version": 1,
        
        // Optional: This will be passed to both pre- and postbuild operations. Can be left out if neither of those is set
        "user_defined_config":
        {
            // The object can contain any user defined sub-objects/attributes
            "any": "Any Value",
            "my_fancy_object":
            {
                "my_list": ["Just", "some", "text"]
            }
        },
        
        // Mandatory: Tools used for building the application
        "build_tools":
        {   
            // Mandatory: Contains informations about MSBuild.exe (currently paths)
            "msbuild":
            {
                // Mandatory: An array of paths, wherein the script will search for msbuild. The first (!) MSBuild.exe found will be used 
                "paths": [
                            // It can be a path to any directory
                            "A\\path\\to\\recursively\\search\\for\\msbuild",
                            
                            // A direct path to MSBuild.exe
                            "A\\direct\\path\\to\\MSBuild.exe",
                            
                            // Environment variables will be expanded
                            "%ProgramFiles%\\a\\path\\containing\\env\\vars"
                         ]
            },
            
            // Mandatory / Optional:
            // The script will search the solution dir (see: 'solution') for 'packages.config'. If one is found, the script
            // will assume, that nuget is used. In this case 'nuget.exe' will be called to fetch dependencies before the build.
            // If the solution does not contain a 'packages.cofig', this can be left out.
            "nuget":
            {
                // The same rules as in the paths for MSBuild.exe apply
                "paths": [
                            "A\\path\\to\\recursively\\search\\for\\nuget",
                            "A\\direct\\path\\to\\nuget.exe",
                            "%ProgramFiles%\\a\\path\\containing\\env\\vars"
                         ]
            }
        },
        
        // Mandatory: Configuration for the solution
        "solution":
        {
            // Mandatory: The name of the solution, actual value does not matter
            "name": "The name of the solution",
            
            // Mandatory: The path to the solution file
            "path": "the\\path\\to\\the\\solution.sln",
            
            // Mandatory: The projects inside the solution
            "projects":
            [
                {
                    // Mandatory: The configuration for one specific project
                    "project":
                    {
                        // Mandatory: The name of the project, actual value does not matter
                        "name": "The name of the project in the solution",
                        
                        // Mandatory: The path to the project in the solution
                        "path": "the\\path\\to\\project.csproj",
                        
                        // Mandatory: The build properties passed to MSBuild.exe
                        "build_properties":
                        {
                            // The actual properties here can by any valid MSBuild project properties:
                            // see also: https://docs.microsoft.com/en-us/visualstudio/msbuild/common-msbuild-project-properties?view=vs-2017
                            "TargetFrameworkVersion": "4.7.1",
                            "DebugSymbols": "false",
                            "DebugType": "none",
                            "OutputPath": "..\\relative\\to\\solution\\bin\\Release",
                            "Configuration": "Release"
                        }
                    }
                }
            ]
        }
        
        // An optional object called 'logging' can be here, to configure python logging module. If none is specified
        // the script will be configured as 'logging.basicConfig(level=logging.INFO)'.
    }
    
## Script Usage

    # The configurator reads the json file. The default path/name is './build.config.json'
    config = Configurator()
    # Create the MSBuilder, 'config' is mandatory, pre- and postbuild are optional
    builder = MsBuilder(config, prebuild=prebuild, postbuild=postbuild)
    # Build the solution according to the configuration json
    builder.build()
    
### Pre- and Postbuild callbacks

Pre- and postbuild steps are optional and can be passed the the `MsBuilder`. Both functions must return `True\False` to indicate their result to the `MsBuilder`. If the `prebuild`-callback returns `False`, the build will be aborted. The `postbuild`-callback will be called after a successfull build.

Both pre- and postbuild callbacks need to take one parameter, the `user_defined_config` specified in the `build.config.json`
    
    # An example for a postbuild callback
    def prebuild(user_defined_config):

        error = prepare_files()
        
        # ... access config
        my_conf = user_defined_config['my_fancy_object']
        
        do_something_with(my_conf)
        
        if error
            return False
        return True
