package com.orderdelivery.deliveryservice.service;

import com.orderdelivery.deliveryservice.entity.Rider;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class RiderMatcherTest {

    private final RiderMatcher matcher = new RiderMatcher();

    // Austin city centroid is (30.2672, -97.7431)
    private static final double AUSTIN_LAT = 30.2672;
    private static final double AUSTIN_LON = -97.7431;

    private Rider riderAt(double lat, double lon) {
        return new Rider("Test", "Rider", "555-0000", "bike", "Austin", new BigDecimal("4.5"),
                LocalDate.now(), BigDecimal.valueOf(lat), BigDecimal.valueOf(lon));
    }

    @Test
    void picksCloserRider_whenWorkloadEqual() {
        Rider near = riderAt(30.2700, -97.7400); // ~0.4km from destination
        Rider far = riderAt(30.4000, -97.9000);  // ~20km from destination

        Optional<RiderMatcher.Candidate> best = matcher.selectBestRider(
                List.of(near, far), AUSTIN_LAT, AUSTIN_LON, r -> 0L);

        assertThat(best).isPresent();
        assertThat(best.get().rider()).isSameAs(near);
    }

    @Test
    void picksLessBusyRider_whenDistanceEqual() {
        Rider sameSpot1 = riderAt(AUSTIN_LAT, AUSTIN_LON);
        Rider sameSpot2 = riderAt(AUSTIN_LAT, AUSTIN_LON);

        Optional<RiderMatcher.Candidate> best = matcher.selectBestRider(
                List.of(sameSpot1, sameSpot2), AUSTIN_LAT, AUSTIN_LON,
                r -> r == sameSpot1 ? 3L : 0L);

        assertThat(best).isPresent();
        assertThat(best.get().rider()).isSameAs(sameSpot2);
    }

    @Test
    void workloadCanOutweighSmallDistanceAdvantage() {
        // near rider is 1km closer but carrying 3 active deliveries (3 * 2.0 = 6.0 penalty, dwarfs 1km)
        Rider nearButBusy = riderAt(30.2762, -97.7431); // ~1km north
        Rider fartherButFree = riderAt(30.2672, -97.7431); // at the destination itself

        Optional<RiderMatcher.Candidate> best = matcher.selectBestRider(
                List.of(nearButBusy, fartherButFree), AUSTIN_LAT, AUSTIN_LON,
                r -> r == nearButBusy ? 3L : 0L);

        assertThat(best).isPresent();
        assertThat(best.get().rider()).isSameAs(fartherButFree);
    }

    @Test
    void fallsBackToCityCentroid_whenRiderHasNoCurrentPosition() {
        Rider noGps = new Rider("Test", "Rider", "555-0000", "bike", "Austin", new BigDecimal("4.5"),
                LocalDate.now(), null, null);

        Optional<RiderMatcher.Candidate> best = matcher.selectBestRider(
                List.of(noGps), AUSTIN_LAT, AUSTIN_LON, r -> 0L);

        assertThat(best).isPresent();
        // distance from Austin centroid to Austin centroid should be ~0
        assertThat(best.get().distanceKm()).isLessThan(0.01);
    }

    @Test
    void emptyCandidateList_returnsEmpty() {
        assertThat(matcher.selectBestRider(List.of(), AUSTIN_LAT, AUSTIN_LON, r -> 0L)).isEmpty();
    }

    @Test
    void haversine_knownDistance_austinToDenver_isApproximatelyCorrect() {
        // Austin (30.2672,-97.7431) to Denver (39.7392,-104.9903) is ~1300km great-circle
        double distance = RiderMatcher.haversineKm(30.2672, -97.7431, 39.7392, -104.9903);
        assertThat(distance).isBetween(1200.0, 1400.0);
    }
}
