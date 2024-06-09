from . import functions, formatting

from .classes import IncFile, MainResults

import pkg_resources

stream = pkg_resources.resource_stream(__name__, 'geofiles/bypass_lines.csv')
stream = pkg_resources.resource_stream(__name__, 'geofiles/2024 BalmorelMap.geojson')