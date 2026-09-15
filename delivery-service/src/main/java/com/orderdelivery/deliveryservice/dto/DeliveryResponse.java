package com.orderdelivery.deliveryservice.dto;

import com.orderdelivery.deliveryservice.entity.Delivery;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public class DeliveryResponse {

    private final Long deliveryId;
    private final Long orderId;
    private final Long riderId;
    private final LocalDateTime assignedAt;
    private final LocalDateTime pickedUpAt;
    private final LocalDateTime deliveredAt;
    private final String deliveryStatus;
    private final BigDecimal distanceKm;

    public DeliveryResponse(Long deliveryId, Long orderId, Long riderId, LocalDateTime assignedAt,
                             LocalDateTime pickedUpAt, LocalDateTime deliveredAt, String deliveryStatus,
                             BigDecimal distanceKm) {
        this.deliveryId = deliveryId;
        this.orderId = orderId;
        this.riderId = riderId;
        this.assignedAt = assignedAt;
        this.pickedUpAt = pickedUpAt;
        this.deliveredAt = deliveredAt;
        this.deliveryStatus = deliveryStatus;
        this.distanceKm = distanceKm;
    }

    public static DeliveryResponse from(Delivery d) {
        return new DeliveryResponse(d.getDeliveryId(), d.getOrderId(), d.getRiderId(), d.getAssignedAt(),
                d.getPickedUpAt(), d.getDeliveredAt(), d.getDeliveryStatus().name(), d.getDistanceKm());
    }

    public Long getDeliveryId() {
        return deliveryId;
    }

    public Long getOrderId() {
        return orderId;
    }

    public Long getRiderId() {
        return riderId;
    }

    public LocalDateTime getAssignedAt() {
        return assignedAt;
    }

    public LocalDateTime getPickedUpAt() {
        return pickedUpAt;
    }

    public LocalDateTime getDeliveredAt() {
        return deliveredAt;
    }

    public String getDeliveryStatus() {
        return deliveryStatus;
    }

    public BigDecimal getDistanceKm() {
        return distanceKm;
    }
}
