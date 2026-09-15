package com.orderdelivery.deliveryservice.repository;

import com.orderdelivery.deliveryservice.entity.Delivery;
import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface DeliveryRepository extends JpaRepository<Delivery, Long> {
    Optional<Delivery> findByOrderId(Long orderId);

    /**
     * One query for every candidate rider's current active-delivery count,
     * grouped by rider - used by rider-matching to score N candidates
     * without issuing N separate COUNT queries (see RiderWorkloadCount /
     * DeliveryService.assignRider). Riders with zero matching deliveries
     * simply have no row in the result, not a zero row - callers must
     * default missing entries to 0.
     */
    @Query("SELECT d.riderId AS riderId, COUNT(d) AS activeCount FROM Delivery d " +
            "WHERE d.riderId IN :riderIds AND d.deliveryStatus IN :statuses GROUP BY d.riderId")
    List<RiderWorkloadCount> countActiveDeliveriesGroupedByRider(
            @Param("riderIds") Collection<Long> riderIds,
            @Param("statuses") Collection<DeliveryStatus> statuses);

    interface RiderWorkloadCount {
        Long getRiderId();

        Long getActiveCount();
    }
}
