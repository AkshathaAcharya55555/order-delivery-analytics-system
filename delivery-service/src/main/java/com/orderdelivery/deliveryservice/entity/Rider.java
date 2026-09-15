package com.orderdelivery.deliveryservice.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "riders")
public class Rider {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "rider_id")
    private Long riderId;

    @Column(name = "first_name", nullable = false)
    private String firstName;

    @Column(name = "last_name", nullable = false)
    private String lastName;

    @Column(name = "phone", nullable = false)
    private String phone;

    @Column(name = "vehicle_type", nullable = false)
    private String vehicleType;

    @Column(name = "city", nullable = false)
    private String city;

    @Column(name = "rating")
    private BigDecimal rating;

    @Column(name = "is_active", nullable = false)
    private boolean active = true;

    @Column(name = "is_available", nullable = false)
    private boolean available = true;

    @Column(name = "current_latitude")
    private BigDecimal currentLatitude;

    @Column(name = "current_longitude")
    private BigDecimal currentLongitude;

    @Column(name = "joined_date", nullable = false)
    private LocalDate joinedDate;

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;

    protected Rider() {
    }

    public Rider(String firstName, String lastName, String phone, String vehicleType, String city,
                 BigDecimal rating, LocalDate joinedDate, BigDecimal currentLatitude, BigDecimal currentLongitude) {
        this.firstName = firstName;
        this.lastName = lastName;
        this.phone = phone;
        this.vehicleType = vehicleType;
        this.city = city;
        this.rating = rating;
        this.joinedDate = joinedDate;
        this.currentLatitude = currentLatitude;
        this.currentLongitude = currentLongitude;
    }

    public Long getRiderId() {
        return riderId;
    }

    public String getFirstName() {
        return firstName;
    }

    public String getLastName() {
        return lastName;
    }

    public String getPhone() {
        return phone;
    }

    public String getVehicleType() {
        return vehicleType;
    }

    public String getCity() {
        return city;
    }

    public BigDecimal getRating() {
        return rating;
    }

    public boolean isActive() {
        return active;
    }

    public boolean isAvailable() {
        return available;
    }

    public void setAvailable(boolean available) {
        this.available = available;
    }

    public BigDecimal getCurrentLatitude() {
        return currentLatitude;
    }

    public BigDecimal getCurrentLongitude() {
        return currentLongitude;
    }

    public LocalDate getJoinedDate() {
        return joinedDate;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
