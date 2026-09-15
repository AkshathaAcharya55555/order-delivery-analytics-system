package com.orderdelivery.deliveryservice.model;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

/**
 * deliveries.delivery_status is stored lowercase in the DB (assigned,
 * picked_up, out_for_delivery, delivered, failed) while the Java enum uses
 * conventional uppercase constants — this converter bridges the two.
 */
@Converter(autoApply = true)
public class DeliveryStatusConverter implements AttributeConverter<DeliveryStatus, String> {

    @Override
    public String convertToDatabaseColumn(DeliveryStatus attribute) {
        return attribute == null ? null : attribute.name().toLowerCase();
    }

    @Override
    public DeliveryStatus convertToEntityAttribute(String dbData) {
        return dbData == null ? null : DeliveryStatus.valueOf(dbData.toUpperCase());
    }
}
