package com.orderdelivery.deliveryservice.model;

import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

/**
 * Delivery-leg status. Matches deliveries.delivery_status's CHECK constraint
 * values (stored lowercase in the DB — see DeliveryStatusConverter).
 */
public enum DeliveryStatus {
    ASSIGNED,
    PICKED_UP,
    OUT_FOR_DELIVERY,
    DELIVERED,
    FAILED;

    private static final Map<DeliveryStatus, Set<DeliveryStatus>> NEXT = Map.of(
            ASSIGNED, EnumSet.of(PICKED_UP, FAILED),
            PICKED_UP, EnumSet.of(OUT_FOR_DELIVERY, FAILED),
            OUT_FOR_DELIVERY, EnumSet.of(DELIVERED, FAILED),
            DELIVERED, EnumSet.noneOf(DeliveryStatus.class),
            FAILED, EnumSet.noneOf(DeliveryStatus.class)
    );

    public boolean canTransitionTo(DeliveryStatus next) {
        return NEXT.getOrDefault(this, Set.of()).contains(next);
    }

    /** The order-level status (same vocabulary as OrderStatus) this delivery status corresponds to. */
    public OrderStatus toOrderStatus() {
        return OrderStatus.valueOf(this.name());
    }
}
