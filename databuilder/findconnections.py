
import simplejson as json
import sys

runs = json.load(file("muniruns.json"))
stops = json.load(file("munistops.json"))

start_stop_id = sys.argv[1]
end_stop_id = sys.argv[2]

def main():

    start_stop = stops[start_stop_id]
    end_stop = stops[end_stop_id]

    print "Start stop is %s with %r" % (start_stop["name"], start_stop["runs"])
    print "End stop is %s with %r" % (end_stop["name"], end_stop["runs"])

    for route in options(start_stop_id, end_stop_id):

        if not route_is_possible(route):
            continue
        
        print "-----------"
        for hop in route:
            print hop.in_english()

class Hop:
    def __init__(self, start_stop_id, end_stop_id, run_id):
        self.start_stop_id = start_stop_id
        self.end_stop_id = end_stop_id
        self.run_id = run_id

    def __repr__(self):
        return repr([self.start_stop_id, self.end_stop_id, self.run_id])

    def in_english(self):
        if self.run_id:
            route = runs[self.run_id]["route"]
            start_stop_name = stops[self.start_stop_id]["name"]
            end_stop_name = stops[self.end_stop_id]["name"]
            return "Take %s (%s) from %s to %s" % (route, self.run_id, start_stop_name, end_stop_name)
        else:
            start_stop_name = stops[self.start_stop_id]["name"]
            end_stop_name = stops[self.end_stop_id]["name"]
            return "Walk from %s to %s" % (start_stop_name, end_stop_name)


def options(start_stop_id, end_stop_id, try_nearby_stops=True, runs_already_used=None):

    start_stop = stops[start_stop_id]
    end_stop = stops[end_stop_id]

    start_stop_transfers = json.load(file("transfers/%s-out.json" % start_stop_id))
    end_stop_transfers = json.load(file("transfers/%s-out.json" % end_stop_id))

    target_runs = end_stop_transfers["at_this_stop"].keys()

    if runs_already_used is None:
        runs_already_used = {}

    for run_id in target_runs:
        if run_id in start_stop_transfers["at_this_stop"]:
            runs_already_used[run_id] = True
            yield (Hop(start_stop_id, end_stop_id, run_id),)

    for run_id in target_runs:
        if run_id in start_stop_transfers["direct_transfers"]:
            transfers = start_stop_transfers["direct_transfers"][run_id]
            for transfer in transfers:
                transfer_stop_id = transfer["transfer_at"]
                first_run_id = transfer["first_take"]
                first_hop = Hop(start_stop_id, transfer_stop_id, first_run_id)
                second_hop = Hop(transfer_stop_id, end_stop_id, run_id)

                runs_already_used[first_run_id] = True
                runs_already_used[run_id] = True

                yield (first_hop, second_hop)

    for run_id in target_runs:
        if run_id in start_stop_transfers["walking_transfers"]:
            transfers = start_stop_transfers["walking_transfers"][run_id]
            for transfer in transfers:
                get_off_stop_id = transfer["get_off_at"]
                get_on_stop_id = transfer["get_on_at"]
                first_run_id = transfer["first_take"]
                first_hop = Hop(start_stop_id, get_off_stop_id, first_run_id)
                walking_hop = Hop(get_off_stop_id, get_on_stop_id, None)
                second_hop = Hop(get_on_stop_id, end_stop_id, run_id)

                # Don't return results where the first and second hop
                # are with the same route.
                if runs[first_run_id]["route"] == runs[run_id]["route"]:
                    continue

                # Don't return results that have us take a run that
                # we already returned a more direct result for.
                if run_id in runs_already_used:
                    continue

                runs_already_used[first_run_id] = True
                runs_already_used[run_id] = True

                yield (first_hop, walking_hop, second_hop)

    # Try nearby stops if we're allowed to.
    # (that is, unless we're already doing that.)
    if try_nearby_stops:
        for nearby_stop_id in end_stop_transfers["nearby_stops"]:
            for route in options(start_stop_id, nearby_stop_id, try_nearby_stops=False, runs_already_used=runs_already_used):
                yield route
        for nearby_stop_id in start_stop_transfers["nearby_stops"]:
            for route in options(nearby_stop_id, start_stop_id, try_nearby_stops=False, runs_already_used=runs_already_used):
                yield route

# Given a route, determine if it has any hops where
# backwards travel is required. Returns false if so.
def route_is_possible(route):
    for hop in route:

        run_id = hop.run_id
        start_stop_id = hop.start_stop_id
        end_stop_id = hop.end_stop_id

        # Walking hops are bidirectional.
        if not run_id:
            continue

        for stop_id in reversed(runs[hop.run_id]["stops"]):
            if stop_id == start_stop_id:
                return False
            elif stop_id == end_stop_id:
                # This hop is fine, so check the next
                break

    return True

main()
