
import simplejson as json
import sys

runs = json.load(file("muniruns.json"))
stops = json.load(file("munistops.json"))

start_stop_id = sys.argv[1]
end_stop_id = sys.argv[2]

start_stop = stops[start_stop_id]
end_stop = stops[end_stop_id]

start_stop_transfers = json.load(file("transfers/%s-out.json" % start_stop_id))
end_stop_transfers = json.load(file("transfers/%s-out.json" % end_stop_id))

def main():

    print "Start stop is %s with %r" % (start_stop["name"], start_stop["runs"])
    print "End stop is %s with %r" % (end_stop["name"], end_stop["runs"])

    for route in options():
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
            return "Take %s from %s to %s" % (route, start_stop_name, end_stop_name)
        else:
            start_stop_name = stops[self.start_stop_id]["name"]
            end_stop_name = stops[self.end_stop_id]["name"]
            return "Walk from %s to %s" % (start_stop_name, end_stop_name)


def options():

    target_runs = end_stop_transfers["at_this_stop"].keys()

    for run_id in target_runs:
        if run_id in start_stop_transfers["at_this_stop"]:
            yield (Hop(start_stop_id, end_stop_id, run_id),)

    for run_id in target_runs:
        if run_id in start_stop_transfers["direct_transfers"]:
            transfers = start_stop_transfers["direct_transfers"][run_id]
            for transfer in transfers:
                transfer_stop_id = transfer["transfer_at"]
                first_run_id = transfer["first_take"]
                first_hop = Hop(start_stop_id, transfer_stop_id, first_run_id)
                second_hop = Hop(transfer_stop_id, end_stop_id, run_id)
                # FIXME: need to filter out cases where the
                # transfer stop is after the target stop in the run
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
                # FIXME: need to filter out cases where the
                # transfer stops are after the target stop in the run
                yield (first_hop, walking_hop, second_hop)

def filter_prior_stops(run_id, start_stop_id, end_stop_ids):

    ret = []

    for stop_id in reversed(runs[run_id]["stops"]):

        # If we get back to the start stop then we're done
        if stop_id == start_stop_id:
            break

        if stop_id in end_stop_ids:
            ret.append(stop_id)

    return reversed(ret)
        
main()
