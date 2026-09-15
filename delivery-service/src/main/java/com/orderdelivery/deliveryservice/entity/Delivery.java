package com.orderdelivery.deliveryservice.entity;

import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "deliveries")
public class Delivery {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "delivery_id")
    private Long deliveryId;

    @Column(name = "order_id", nullable = false, unique = true)
    private Long orderId;

    @Column(name = "rider_id", nullable = false)
    private Long riderId;

    @Column(name = "assigned_at", nullable = false)
    private LocalDateTime assignedAt;

    @Column(name = "picked_up_at")
    private LocalDateTime pickedUpAt;

    @Column(name = "delivered_at")
    private LocalDateTime deliveredAt;

    @Column(name = "delivery_status", nullable = false, length = 20)
    private DeliveryStatus deliveryStatus;

    @Column(name = "distance_km", precision = 6, scale = 2)
    private BigDecimal distanceKm;

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;

    protected Delivery() {
    }

    public Delivery(Long orderId, Long riderId, LocalDateTime assignedAt, DeliveryStatus deliveryStatus,
                     BigDecimal distanceKm) {
        this.orderId = orderId;
        this.riderId = riderId;
        this.assignedAt = assignedAt;
        this.deliveryStatus = deliveryStatus;
        this.distanceKm = distanceKm;
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

    public void setPickedUpAt(LocalDateTime pickedUpAt) {
        this.pickedUpAt = pickedUpAt;
    }

    public LocalDateTime getDeliveredAt() {
        return deliveredAt;
    }

    public void setDeliveredAt(LocalDateTime deliveredAt) {
        this.deliveredAt = deliveredAt;
    }

    public DeliveryStatus getDeliveryStatus() {
        return deliveryStatus;
    }

    public void setDeliveryStatus(DeliveryStatus deliveryStatus) {
        this.deliveryStatus = deliveryStatus;
    }

    public BigDecimal getDistanceKm() {
        return distanceKm;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
