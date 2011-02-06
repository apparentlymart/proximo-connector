
use LWP::UserAgent;
use JSON::Any;
use Data::Dumper;

my $ua = LWP::UserAgent->new();
my $json = JSON::Any->new();

my $routes = get_proximo('/routes.json');

my %stops = ();
my %runs = ();

foreach my $route (@{$routes->{items}}) {
    my $route_id = $route->{id};
    my $route_name = $route->{display_name};

    warn "Getting runs for $route_name:\n";

    my $runs = get_proximo("/routes/$route_id/runs.json");

    foreach my $run (@{$runs->{items}}) {

        my $run_id = $run->{id};
        my $run_name = $run->{display_name};

        warn " * $run_name:\n";

        my $stop_ids = [];
        $runs{$run_id} = {
            route => $route_id,
            stops => $stop_ids,
        };

        my $stops = get_proximo("/routes/$route_id/runs/$run_id/stops.json");

        foreach my $stop (@{$stops->{items}}) {
            my $stop_id = $stop->{id};
            my $stop_name = $stop->{display_name};
            my $stop_lat = $stop->{latitude};
            my $stop_lon = $stop->{longitude};

            $stops{$stop_id} ||= {
                name => $stop_name,
                lat => $stop_lat,
                lon => $stop_lon,
                runs => [],
            };
            push @$stop_ids, $stop_id;

            push @{$stops{$stop_id}{runs}}, $run_id;
        }

    }

}

foreach my $stop (values %stops) {
    $stop->{runs} = [ sort @{$stop->{runs}} ];
}

open(OUT, '>', 'munistops.json');
print OUT $json->encode(\%stops);
close(OUT);

open(OUT, '>', 'muniruns.json');
print OUT $json->encode(\%runs);
close(OUT);

sub get_proximo {
    my ($path) = @_;

    my $url = 'http://proximobus.appspot.com/agencies/sf-muni' . $path;
    my $res = $ua->get($url);

    if ($res->is_success) {
        return $json->decode($res->content);
    }
    else {
        die "Failed to retrieve $url: " . $res->status_line;
    }
}
