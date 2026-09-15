package com.orderdelivery.deliveryservice.service;

import com.orderdelivery.deliveryservice.entity.Rider;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.ToLongFunction;

/**
 * Simple, explainable rider-matching algorithm (no ML). Given a pool of
 * already-filtered candidate riders (active, available, in the order's
 * city), picks the one with the lowest weighted score of:
 *
 *   score = DISTANCE_WEIGHT_KM * approxDistanceKm + WORKLOAD_WEIGHT * activeDeliveryCount
 *
 * Lower is better. Distance is "approximate" because riders don't have live
 * GPS tracking in this schema: it uses the rider's last-known
 * current_latitude/current_longitude when available, and falls back to the
 * rider's home-city centroid otherwise (see CITY_CENTROIDS).
 *
 * The weights below are a configured, documented business assumption — each
 * currently-active delivery a rider is carrying is treated as costing as
 * much "unavailability" as 2 extra kilometers of distance. Not measured,
 * not ML — a transparent, adjustable formula.
 */
@Component
public class RiderMatcher {

    static final double DISTANCE_WEIGHT_KM = 1.0;
    static final double WORKLOAD_WEIGHT_PER_ACTIVE_DELIVERY = 2.0;

    static final Map<String, double[]> CITY_CENTROIDS = Map.of(
            "Austin", new double[]{30.2672, -97.7431},
            "Denver", new double[]{39.7392, -104.9903},
            "Portland", new double[]{45.5152, -122.6784},
            "Chicago", new double[]{41.8781, -87.6298},
            "Miami", new double[]{25.7617, -80.1918},
            "Seattle", new double[]{47.6062, -122.3321}
    );

    public record Candidate(Rider rider, double distanceKm, long activeDeliveries, double score) {
    }

    /**
     * @param candidates       riders already filtered to active + available + same city
     * @param orderLatitude    delivery destination latitude
     * @param orderLongitude   delivery destination longitude
     * @param workloadOf       returns the rider's current count of active (assigned/picked_up/out_for_delivery) deliveries
     */
    public Optional<Candidate> selectBestRider(List<Rider> candidates, double orderLatitude, double orderLongitude,
                                                ToLongFunction<Rider> workloadOf) {
        return candidates.stream()
                .map(rider -> score(rider, orderLatitude, orderLongitude, workloadOf.applyAsLong(rider)))
                .min((a, b) -> Double.compare(a.score(), b.score()));
    }

    private Candidate score(Rider rider, double orderLat, double orderLon, long activeDeliveries) {
        double[] position = riderPosition(rider);
        double distanceKm = haversineKm(position[0], position[1], orderLat, orderLon);
        double score = DISTANCE_WEIGHT_KM * distanceKm + WORKLOAD_WEIGHT_PER_ACTIVE_DELIVERY * activeDeliveries;
        return new Candidate(rider, distanceKm, activeDeliveries, score);
    }

    private double[] riderPosition(Rider rider) {
        if (rider.getCurrentLatitude() != null && rider.getCurrentLongitude() != null) {
            return new double[]{rider.getCurrentLatitude().doubleValue(), rider.getCurrentLongitude().doubleValue()};
        }
        double[] centroid = CITY_CENTROIDS.get(rider.getCity());
        if (centroid == null) {
            throw new IllegalStateException("No known centroid for city: " + rider.getCity());
        }
        return centroid;
    }

    /** Great-circle distance in kilometers between two lat/lon points. */
    static double haversineKm(double lat1, double lon1, double lat2, double lon2) {
        final double earthRadiusKm = 6371.0;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return earthRadiusKm * c;
    }
}
