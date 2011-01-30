
from graphserver.graphdb import GraphDatabase
from graphserver.core import State, WalkOptions, Street
from graphserver.ext.osm.osmdb import OSMDB

import time
import sys
import graphserver
import os
from graphserver.util import TimeHelpers
import sqlite3
try:
    import json
except ImportError:
    import simplejson as json

graphdb_filename = "sanfrancisco.gdb"
osmdb_filename = "sanfrancisco.osmdb"
munistops_filename = "munistops.json"
munistopsdb_filename = "munistops.db"

starttime = 0
lat_adj_tolerance = 0.002
lon_adj_tolerance = 0.002
walk_adj_tolerance = 180 # 3 minutes

munistops = json.load(file(munistops_filename))
graphdb = GraphDatabase( graphdb_filename )
graph = graphdb.incarnate()
osmdb = OSMDB( osmdb_filename )
try:
    os.remove(munistopsdb_filename)
except OSError:
    pass
munistopsdb = sqlite3.connect(munistopsdb_filename)

def main():

    set_up_munistopsdb_schema()

    pairs = 0

    for start_stop_id, end_stop_id in adjacent_muni_stops_by_coords():
        start_stop = munistops[start_stop_id]
        end_stop = munistops[end_stop_id]
        walk = get_walk( start_stop["lat"], start_stop["lon"], end_stop["lat"], end_stop["lon"] )
        if walk is None:
            continue
        walk_time = walk.time

        if walk_time <= walk_adj_tolerance:
            #print "%s and %s are adjacent, with %.2f minute, %.2f mile walk along %r" % (start_stop["name"], end_stop["name"], walk_time / 60.0, walk.distance, walk.points)
            #print "%r vs. %r" % (start_stop["runs"], end_stop["runs"])

            add_transfer_to_munistopsdb( start_stop_id, end_stop_id, walk_time, walk.distance, walk.points )

        pairs = pairs + 1

        if (pairs % 100) == 0:
            percent = (pairs / 32000) * 100
            print "Pair %i (~%.3f%%)" % (pairs, percent)

    print "There are %i pairs total" % pairs

    #walk_time = get_walk_time(lat1, lon1, lat2, lon2)

    #print "Walk time is %.3f minutes" % (walk_time / 60.0)

def adjacent_muni_stops_by_coords():
    for start_stop_id in munistops:

        start_stop = munistops[start_stop_id]

        add_stop_to_munistopsdb( start_stop_id, start_stop["name"], start_stop["lat"], start_stop["lon"] )
        
        for end_stop_id in munistops:
            if start_stop_id == end_stop_id:
                continue
            
            end_stop = munistops[end_stop_id]

            lat_diff = abs(start_stop["lat"] - end_stop["lat"])
            lon_diff = abs(start_stop["lon"] - end_stop["lon"])

            if (lat_diff <= lat_adj_tolerance) and (lon_diff <= lon_adj_tolerance):
                # Don't bother if the two stops serve exactly the same runs,
                # since there'll never be any need to transfer here in that case.
                # (this stops list is saved sorted, so we can just compare here)
                if start_stop["runs"] != end_stop["runs"]:
                    yield (start_stop_id, end_stop_id)

class Walk:
    pass

def get_walk( lat1, lon1, lat2, lon2 ):
    vertex1 = get_nearest_vertex( lat1, lon1 )
    vertex2 = get_nearest_vertex( lat2, lon2 )

    wo = WalkOptions()
    wo.transfer_penalty = 0
    wo.walking_speed = 1.0
    wo.hill_reluctance = 1.5

    try:
        spt = graph.shortest_path_tree( vertex1, vertex2, State(1, starttime), wo )
        vertices, edges = spt.path( vertex2 )
    except Exception:
        print "couldn't find a path between (%.4f,%4f) and (%.4f,%.4f)" % ( lat1, lon1, lat2, lon2)
        return None

    first_walk_time = None
    last_walk_time = None
    walk_streets = []
    walk_points = []
    walk_distance = 0

    for edge1,vertex1,edge2,vertex2 in zip( [None]+edges, vertices, edges+[None], vertices[1:]+[None,None] ):

        edge1payload = edge1.payload if edge1 else None
        edge2payload = edge2.payload if edge2 else None

        if edge2 is not None and isinstance(edge2.payload, Street):

            # Add the street geometry for this edge to our walk_points
            geometry_chunk = osmdb.edge( edge2.payload.name )[5]

            if edge2.payload.reverse_of_source:
                walk_points.extend( reversed( geometry_chunk ) )
            else:
                walk_points.extend( geometry_chunk )

            # Add this edge's distance in meters to the walk_distance
            walk_distance += edge2.payload.length

        if edge1 and edge2 and isinstance(edge1.payload, Street) and edge1.payload.way != edge2.payload.way:

            # We hit a turn

            walk_streets.append(get_street_name_for_edge(edge2))

        if (edge1 is None or not isinstance(edge1.payload, Street)) and (edge2 and isinstance(edge2.payload, Street)):

            # We started walking

            walk_streets.append(get_street_name_for_edge(edge2))

            if first_walk_time is None:
                first_walk_time = vertex1.state.time

        if (edge1 and isinstance(edge1.payload, Street)) and (edge2 is None or not isinstance(edge2.payload, Street)):

            # We stopped walking

            last_walk_time = vertex1.state.time

    if first_walk_time is None or last_walk_time is None:
        walk_time = 0
    else:
        walk_time = last_walk_time - first_walk_time

    ret = Walk()
    ret.time = walk_time
    ret.streets = walk_streets
    ret.points = walk_points
    ret.distance = walk_distance / 1609.344 # convert to miles

    return ret

def get_nearest_vertex( lat, lon ):
    nearby_vertices = list(osmdb.nearest_node(lat, lon))
    return "osm-%s" % nearby_vertices[0]

def get_street_name_for_edge( edge ):
    if edge:
        osm_way = edge.payload.name.split("-")[0]
        street_name = osmdb.way( osm_way ).tags.get('name', 'unnamed street')
        return street_name
        
    else:
        return None

def set_up_munistopsdb_schema():

    db = munistopsdb
    c = db.cursor()

    c.execute("CREATE TABLE stop (stop_id INTEGER, name TEXT, lat FLOAT, lon FLOAT)")
    c.execute("CREATE TABLE transfer (start_stop_id INTEGER, end_stop_id INTEGER, time FLOAT, distance FLOAT, points TEXT) ")
    db.commit()
    c.close()

def set_up_munistopsdb_indices():

    db = munistopsdb
    c = db.cursor()

    c.execute("CREATE INDEX id ON stop (stop_id)");
    c.execute("CREATE INDEX start ON transfer (start_stop_id)");
    c.execute("CREATE INDEX end ON transfer (end_stop_id)");

    db.commit()
    c.close()

def add_stop_to_munistopsdb( stop_id, name, lat, lon ):
    db = munistopsdb
    c = db.cursor()

    c.execute("INSERT INTO stop (stop_id, name, lat, lon) VALUES (?, ?, ?, ?)", (stop_id, name, lat, lon));

    db.commit()
    c.close()

def add_transfer_to_munistopsdb( start_stop_id, end_stop_id, time, distance, points ):
    db = munistopsdb
    c = db.cursor()

    points_raw = json.dumps(points)

    c.execute("INSERT INTO transfer (start_stop_id, end_stop_id, time, distance, points) VALUES (?, ?, ?, ?, ?)", (start_stop_id, end_stop_id, time, distance, points_raw))

    db.commit()
    c.close()
    
main()
