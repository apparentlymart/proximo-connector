#!/usr/bin/perl

use strict;
use warnings;

use JSON::Any;
use DBI;

my $json = JSON::Any->new();

my $stops = load_json("munistops.json");
my $runs = load_json("muniruns.json");
my $transfers_dbh = DBI->connect("dbi:SQLite:dbname=munistops.db","","") || die "Failed to open munistops.db";

foreach my $stop_id (keys %$stops) {

    next unless $stop_id == 14958;

    my $stop = $stops->{$stop_id};

    my $at_this_stop = {};
    my $direct_transfers = {};
    my $walking_transfers = {};

    # "at this stop" is easy
    foreach my $run_id (@{$stop->{runs}}) {
        $at_this_stop->{$run_id} = $json->true,
    }

    # Now build direct_transfers by walking each of the
    # runs available at this stop.
    foreach my $run_id (@{$stop->{runs}}) {
        my $run = $runs->{$run_id};
        next unless $run;

        my $found_my_stop = 0;

        my $last_runs = {};

        foreach my $other_stop_id (@{$run->{stops}}) {

            # Ignore all of the stops that come before
            # our reference stop, since we'd have to
            # ride the bus backwards to get to them.
            if ($other_stop_id eq $stop_id) {
                $found_my_stop = 1;
                next;
            }
            next unless $found_my_stop;

            my $other_stop = $stops->{$other_stop_id};
            my $other_run_ids = $other_stop->{runs};

            my $new_last_runs = {};

            foreach my $other_run_id (@$other_run_ids) {
                # Don't bother recording transfers
                # to lines that are at this stop already anyway.
                next if $at_this_stop->{$other_run_id};

                # Also don't bother recording a transfer
                # that we documented at the previous stop.
                # Otherwise we get data bloat when
                # two runs share the same street for a stretch.
                next if $last_runs->{$other_run_id};

                $direct_transfers->{$other_run_id} ||= [];

                push @{$direct_transfers->{$other_run_id}}, {
                    transfer_at => $other_stop_id,
                };

                $new_last_runs->{$other_run_id} = 1;
            }

            $last_runs = $new_last_runs;
        }
    }

    # Now one more walk to build walking_transfers.
    # This is done as a separate walk so we can exclude
    # transfers to runs that already have a direct transfer.
    foreach my $run_id (@{$stop->{runs}}) {
        my $run = $runs->{$run_id};
        next unless $run;

        my $found_my_stop = 0;

        foreach my $off_stop_id (@{$run->{stops}}) {

            # Ignore all of the stops that come before
            # our reference stop, since we'd have to
            # ride the bus backwards to get to them.
            # Unlike for direct transfers, we *do*
            # include walking transfers from the
            # reference stop.
            if ($off_stop_id eq $stop_id) {
                $found_my_stop = 1;
            }
            next unless $found_my_stop;

            my $off_stop = $stops->{$off_stop_id};

            # Use the transfers DB to find adjacent stops
            my $sth = $transfers_dbh->prepare("SELECT end_stop_id, distance, points FROM transfer WHERE start_stop_id = ? ORDER BY distance");
            $sth->execute($off_stop_id);

            my $distance_for_run = {};

            while (my ($on_stop_id, $distance, $points) = $sth->fetchrow_array()) {
                my $on_stop = $stops->{$on_stop_id};

                foreach my $other_run_id (@{$on_stop->{runs}}) {
                    
                    # Ignore runs that are already at this stop
                    next if $at_this_stop->{$other_run_id};
                    
                    # Ignore runs that we can get to by direct transfer
                    next if $direct_transfers->{$other_run_id};

                    if (exists($distance_for_run->{$other_run_id})) {
                        my $prev_distance = $distance_for_run->{$other_run_id};
                        next if $distance > $prev_distance;
                    }

                    $walking_transfers->{$other_run_id} ||= [];

                    push @{$walking_transfers->{$other_run_id}}, {
                        get_off_at => $off_stop_id,
                        get_on_at => $on_stop_id,
                        distance => $distance,
                    };
                    
                    $distance_for_run->{$other_run_id} = $distance;
                }
            }

        }

    }

    my $data = {
        at_this_stop => $at_this_stop,
        direct_transfers => $direct_transfers,
        walking_transfers => $walking_transfers,
    };

    my $fn = "transfers/${stop_id}-out.json";
    open(my $out, '>', $fn) || die "Failed to open $fn for writing: $!";
    print $out $json->encode($data);
    close($out);

}

sub load_json {
    my ($fn) = @_;

    open(my $in, '<', $fn) || die "Can't open $fn for reading: $!";
    my $data = join('', <$in>);
    close($in);

    return $json->decode($data);
}
