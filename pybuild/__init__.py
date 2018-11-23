# Import some classes at package level for convenient usage
from pybuild.msbuilder import MsBuilder, Configurator

# A list of 'public objects', that will be imported, when a user types 'from pybuild import *'
__all__ = ['msbuilder']
