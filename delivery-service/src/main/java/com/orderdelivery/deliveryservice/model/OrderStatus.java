package com.orderdelivery.deliveryservice.model;

/**
 * Order lifecycle status. Matches the CHECK constraint values in
 * database/schema.sql (orders.status, order_status_history.status) exactly.
 * Duplicated from order-service since these are independent deployables
 * without a shared library in this project.
 */
public enum OrderStatus {
    PLACED,
    CONFIRMED,
    PREPARING,
    READY_FOR_PICKUP,
    RIDER_ASSIGNED,
    PICKED_UP,
    OUT_FOR_DELIVERY,
    DELIVERED,
    CANCELLED,
    FAILED;

    public boolean isTerminal() {
        return this == DELIVERED || this == CANCELLED || this == FAILED;
    }
}
